using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Runtime.Loader;
using Godot.Bridge;
using Godot.NativeInterop;

namespace GodotPlugins
{
    public static class Main
    {
        // IMPORTANT:
        // Keeping strong references to the AssemblyLoadContext (our PluginLoadContext) prevents
        // it from being unloaded. To avoid issues, we wrap the reference in this class, and mark
        // all the methods that access it as non-inlineable. This way we prevent local references
        // (either real or introduced by the JIT) to escape the scope of these methods due to
        // inlining, which could keep the AssemblyLoadContext alive while trying to unload.
        private sealed class PluginLoadContextWrapper
        {
            private PluginLoadContext? _pluginLoadContext;

            public string? AssemblyLoadedPath
            {
                [MethodImpl(MethodImplOptions.NoInlining)]
                get => _pluginLoadContext?.AssemblyLoadedPath;
            }

            [MethodImpl(MethodImplOptions.NoInlining)]
            public static (Assembly, PluginLoadContextWrapper) CreateAndLoadFromAssemblyName(
                AssemblyName assemblyName,
                string pluginPath,
                ICollection<string> sharedAssemblies,
                AssemblyLoadContext mainLoadContext
            )
            {
                var wrapper = new PluginLoadContextWrapper();
                wrapper._pluginLoadContext = new PluginLoadContext(
                    pluginPath, sharedAssemblies, mainLoadContext);
                var assembly = wrapper._pluginLoadContext.LoadFromAssemblyName(assemblyName);
                return (assembly, wrapper);
            }

            [MethodImpl(MethodImplOptions.NoInlining)]
            public WeakReference CreateWeakReference()
            {
                return new WeakReference(_pluginLoadContext, trackResurrection: true);
            }

            [MethodImpl(MethodImplOptions.NoInlining)]
            internal void Unload()
            {
                _pluginLoadContext?.Unload();
                _pluginLoadContext = null;
            }
        }

        private static readonly List<AssemblyName> SharedAssemblies = new();
        private static readonly Assembly CoreApiAssembly = typeof(Godot.Object).Assembly;
        private static Assembly? _editorApiAssembly;
        private static PluginLoadContextWrapper? _projectLoadContext;

        private static readonly AssemblyLoadContext MainLoadContext =
            AssemblyLoadContext.GetLoadContext(Assembly.GetExecutingAssembly()) ??
            AssemblyLoadContext.Default;

        private static DllImportResolver? _dllImportResolver;

        // Right now we do it this way for simplicity as hot-reload is disabled. It will need to be changed later.
        [UnmanagedCallersOnly]
        // ReSharper disable once UnusedMember.Local
        private static unsafe godot_bool InitializeFromEngine(IntPtr godotDllHandle, godot_bool editorHint,
            PluginsCallbacks* pluginsCallbacks, ManagedCallbacks* managedCallbacks,
            IntPtr unmanagedCallbacks, int unmanagedCallbacksSize)
        {
            try
            {
                _dllImportResolver = new GodotDllImportResolver(godotDllHandle).OnResolveDllImport;

                SharedAssemblies.Add(CoreApiAssembly.GetName());
                NativeLibrary.SetDllImportResolver(CoreApiAssembly, _dllImportResolver);

                AlcReloadCfg.Configure(alcReloadEnabled: editorHint.ToBool());
                NativeFuncs.Initialize(unmanagedCallbacks, unmanagedCallbacksSize);

                if (editorHint.ToBool())
                {
                    _editorApiAssembly = Assembly.Load("GodotSharpEditor");
                    SharedAssemblies.Add(_editorApiAssembly.GetName());
                    NativeLibrary.SetDllImportResolver(_editorApiAssembly, _dllImportResolver);
                }

                *pluginsCallbacks = new()
                {
                    LoadProjectAssemblyCallback = &LoadProjectAssembly,
                    LoadToolsAssemblyCallback = &LoadToolsAssembly,
                    UnloadProjectPluginCallback = &UnloadProjectPlugin,
                };

                *managedCallbacks = ManagedCallbacks.Create();

                return godot_bool.True;
            }
            catch (Exception e)
            {
                Console.Error.WriteLine(e);
                return godot_bool.False;
            }
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct PluginsCallbacks
        {
            public unsafe delegate* unmanaged<char*, godot_string*, godot_bool> LoadProjectAssemblyCallback;
            public unsafe delegate* unmanaged<char*, IntPtr, int, IntPtr> LoadToolsAssemblyCallback;
            public unsafe delegate* unmanaged<godot_bool> UnloadProjectPluginCallback;
        }

        [UnmanagedCallersOnly]
        private static unsafe godot_bool LoadProjectAssembly(char* nAssemblyPath, godot_string* outLoadedAssemblyPath)
        {
            try
            {
                if (_projectLoadContext != null)
                    return godot_bool.True; // Already loaded

                string assemblyPath = new(nAssemblyPath);

                (var projectAssembly, _projectLoadContext) = LoadPlugin(assemblyPath);

                string loadedAssemblyPath = _projectLoadContext.AssemblyLoadedPath ?? assemblyPath;
                *outLoadedAssemblyPath = Marshaling.ConvertStringToNative(loadedAssemblyPath);

                ScriptManagerBridge.LookupScriptsInAssembly(projectAssembly);

                return godot_bool.True;
            }
            catch (Exception e)
            {
                Console.Error.WriteLine(e);
                return godot_bool.False;
            }
        }

        [UnmanagedCallersOnly]
        private static unsafe IntPtr LoadToolsAssembly(char* nAssemblyPath,
            IntPtr unmanagedCallbacks, int unmanagedCallbacksSize)
        {
            try
            {
                string assemblyPath = new(nAssemblyPath);

                if (_editorApiAssembly == null)
                    throw new InvalidOperationException("The Godot editor API assembly is not loaded");

                var (assembly, _) = LoadPlugin(assemblyPath);

                NativeLibrary.SetDllImportResolver(assembly, _dllImportResolver!);

                var method = assembly.GetType("GodotTools.GodotSharpEditor")?
                    .GetMethod("InternalCreateInstance",
                        BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);

                if (method == null)
                {
                    throw new MissingMethodException("GodotTools.GodotSharpEditor",
                        "InternalCreateInstance");
                }

                return (IntPtr?)method
                           .Invoke(null, new object[] { unmanagedCallbacks, unmanagedCallbacksSize })
                       ?? IntPtr.Zero;
            }
            catch (Exception e)
            {
                Console.Error.WriteLine(e);
                return IntPtr.Zero;
            }
        }

        private static (Assembly, PluginLoadContextWrapper) LoadPlugin(string assemblyPath)
        {
            string assemblyName = Path.GetFileNameWithoutExtension(assemblyPath);

            var sharedAssemblies = new List<string>();

            foreach (var sharedAssembly in SharedAssemblies)
            {
                string? sharedAssemblyName = sharedAssembly.Name;
                if (sharedAssemblyName != null)
                    sharedAssemblies.Add(sharedAssemblyName);
            }

            return PluginLoadContextWrapper.CreateAndLoadFromAssemblyName(
                new AssemblyName(assemblyName), assemblyPath, sharedAssemblies, MainLoadContext);
        }

        [UnmanagedCallersOnly]
        private static godot_bool UnloadProjectPlugin()
        {
            try
            {
                return UnloadPlugin(ref _projectLoadContext).ToGodotBool();
            }
            catch (Exception e)
            {
                Console.Error.WriteLine(e);
                return godot_bool.False;
            }
        }

        private static bool UnloadPlugin(ref PluginLoadContextWrapper? pluginLoadContext)
        {
            try
            {
                if (pluginLoadContext == null)
                    return true;

                Console.WriteLine("Unloading assembly load context...");

                var alcWeakReference = pluginLoadContext.CreateWeakReference();

                pluginLoadContext.Unload();
                pluginLoadContext = null;

                int startTimeMs = Environment.TickCount;
                bool takingTooLong = false;

                while (alcWeakReference.IsAlive)
                {
                    GC.Collect(GC.MaxGeneration, GCCollectionMode.Forced);
                    GC.WaitForPendingFinalizers();

                    if (!alcWeakReference.IsAlive)
                        break;

                    int elapsedTimeMs = Environment.TickCount - startTimeMs;

                    if (!takingTooLong && elapsedTimeMs >= 2000)
                    {
                        takingTooLong = true;

                        // TODO: How to log from GodotPlugins? (delegate pointer?)
                        Console.Error.WriteLine("Assembly unloading is taking longer than expected...");
                    }
                    else if (elapsedTimeMs >= 5000)
                    {
                        // TODO: How to log from GodotPlugins? (delegate pointer?)
                        Console.Error.WriteLine(
                            "Failed to unload assemblies. Possible causes: Strong GC handles, running threads, etc.");

                        return false;
                    }
                }

                Console.WriteLine("Assembly load context unloaded successfully.");

                return true;
            }
            catch (Exception e)
            {
                // TODO: How to log exceptions from GodotPlugins? (delegate pointer?)
                Console.Error.WriteLine(e);
                return false;
            }
        }
    }
}
