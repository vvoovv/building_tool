import bpy
from .door import Door
from .door_props import DoorProperty


class BTOOLS_OT_add_door(bpy.types.Operator):
    """Create a door from selected faces"""

    bl_idname = "btools.add_door"
    bl_label = "Add Door"
    bl_options = {"REGISTER", "UNDO"}

    props: bpy.props.PointerProperty(type=DoorProperty)

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.mode == "EDIT_MESH"

    def execute(self, context):
        return Door.build(self.props)

    def draw(self, context):
        self.props.draw(context, self.layout)
