using System;
using System.Diagnostics.CodeAnalysis;

#pragma warning disable CS0169
#pragma warning disable CS0414

namespace Godot.SourceGenerators.Sample
{
    [SuppressMessage("ReSharper", "BuiltInTypeReferenceStyle")]
    [SuppressMessage("ReSharper", "RedundantNameQualifier")]
    [SuppressMessage("ReSharper", "ArrangeObjectCreationWhenTypeEvident")]
    [SuppressMessage("ReSharper", "InconsistentNaming")]
    public partial class ExportedFields : Godot.Object
    {
        [Export] private Boolean field_Boolean = true;
        [Export] private Char field_Char = 'f';
        [Export] private SByte field_SByte = 10;
        [Export] private Int16 field_Int16 = 10;
        [Export] private Int32 field_Int32 = 10;
        [Export] private Int64 field_Int64 = 10;
        [Export] private Byte field_Byte = 10;
        [Export] private UInt16 field_UInt16 = 10;
        [Export] private UInt32 field_UInt32 = 10;
        [Export] private UInt64 field_UInt64 = 10;
        [Export] private Single field_Single = 10;
        [Export] private Double field_Double = 10;
        [Export] private String field_String = "foo";

        // Godot structs
        [Export] private Vector2 field_Vector2 = new(10f, 10f);
        [Export] private Vector2i field_Vector2i = Vector2i.Up;
        [Export] private Rect2 field_Rect2 = new(new Vector2(10f, 10f), new Vector2(10f, 10f));
        [Export] private Rect2i field_Rect2i = new(new Vector2i(10, 10), new Vector2i(10, 10));
        [Export] private Transform2D field_Transform2D = Transform2D.Identity;
        [Export] private Vector3 field_Vector3 = new(10f, 10f, 10f);
        [Export] private Vector3i field_Vector3i = Vector3i.Back;
        [Export] private Basis field_Basis = new Basis(Quaternion.Identity);
        [Export] private Quaternion field_Quaternion = new Quaternion(Basis.Identity);
        [Export] private Transform3D field_Transform3D = Transform3D.Identity;
        [Export] private Vector4 field_Vector4 = new(10f, 10f, 10f, 10f);
        [Export] private Vector4i field_Vector4i = Vector4i.One;
        [Export] private Projection field_Projection = Projection.Identity;
        [Export] private AABB field_AABB = new AABB(10f, 10f, 10f, new Vector3(1f, 1f, 1f));
        [Export] private Color field_Color = Colors.Aquamarine;
        [Export] private Plane field_Plane = Plane.PlaneXZ;
        [Export] private Callable field_Callable = new Callable(Engine.GetMainLoop(), "_process");
        [Export] private SignalInfo field_SignalInfo = new SignalInfo(Engine.GetMainLoop(), "property_list_changed");

        // Enums
        [SuppressMessage("ReSharper", "UnusedMember.Local")]
        enum MyEnum
        {
            A,
            B,
            C
        }

        [Export] private MyEnum field_Enum = MyEnum.C;

        [Flags]
        [SuppressMessage("ReSharper", "UnusedMember.Local")]
        enum MyFlagsEnum
        {
            A,
            B,
            C
        }

        [Export] private MyFlagsEnum field_FlagsEnum = MyFlagsEnum.C;

        // Arrays
        [Export] private Byte[] field_ByteArray = { 0, 1, 2, 3, 4, 5, 6 };
        [Export] private Int32[] field_Int32Array = { 0, 1, 2, 3, 4, 5, 6 };
        [Export] private Int64[] field_Int64Array = { 0, 1, 2, 3, 4, 5, 6 };
        [Export] private Single[] field_SingleArray = { 0f, 1f, 2f, 3f, 4f, 5f, 6f };
        [Export] private Double[] field_DoubleArray = { 0d, 1d, 2d, 3d, 4d, 5d, 6d };
        [Export] private String[] field_StringArray = { "foo", "bar" };
        [Export(PropertyHint.Enum, "A,B,C")] private String[] field_StringArrayEnum = { "foo", "bar" };
        [Export] private Vector2[] field_Vector2Array = { Vector2.Up, Vector2.Down, Vector2.Left, Vector2.Right };
        [Export] private Vector3[] field_Vector3Array = { Vector3.Up, Vector3.Down, Vector3.Left, Vector3.Right };
        [Export] private Color[] field_ColorArray = { Colors.Aqua, Colors.Aquamarine, Colors.Azure, Colors.Beige };
        [Export] private Godot.Object[] field_GodotObjectOrDerivedArray = { null };
        [Export] private StringName[] field_StringNameArray = { "foo", "bar" };
        [Export] private NodePath[] field_NodePathArray = { "foo", "bar" };
        [Export] private RID[] field_RIDArray = { default, default, default };

        // Variant
        [Export] private Variant field_Variant = "foo";

        // Classes
        [Export] private Godot.Object field_GodotObjectOrDerived;
        [Export] private Godot.Texture field_GodotResourceTexture;
        [Export] private StringName field_StringName = new StringName("foo");
        [Export] private NodePath field_NodePath = new NodePath("foo");
        [Export] private RID field_RID;

        [Export] private Godot.Collections.Dictionary field_GodotDictionary =
            new() { { "foo", 10 }, { Vector2.Up, Colors.Chocolate } };

        [Export] private Godot.Collections.Array field_GodotArray =
            new() { "foo", 10, Vector2.Up, Colors.Chocolate };

        [Export] private Godot.Collections.Dictionary<string, bool> field_GodotGenericDictionary =
            new() { { "foo", true }, { "bar", false } };

        [Export] private Godot.Collections.Array<int> field_GodotGenericArray =
            new() { 0, 1, 2, 3, 4, 5, 6 };
    }
}
