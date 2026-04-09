# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import mathutils
from . import shared


def register_props():
    bpy.types.Scene.m3qt_bone_name = bpy.props.StringProperty(
        name='骨骼名称',
        description='新骨骼的名称',
        default='Bone_New',
    )
    bpy.types.Scene.m3qt_parent_bone = bpy.props.StringProperty(
        name='父骨骼',
        description='将新骨骼绑定到的父骨骼',
        default='',
    )
    bpy.types.Scene.m3qt_bone_length = bpy.props.FloatProperty(
        name='骨骼长度',
        description='新骨骼的长度',
        default=0.3,
        min=0.01,
        max=10.0,
    )
    bpy.types.Scene.m3qt_at_cursor = bpy.props.BoolProperty(
        name='在3D游标处创建',
        description='在3D游标位置创建骨骼，而不是在父骨骼尾部',
        default=False,
    )
    bpy.types.Scene.m3qt_create_vgroup = bpy.props.BoolProperty(
        name='创建顶点组',
        description='在所有子网格上创建与骨骼同名的顶点组',
        default=True,
    )
    bpy.types.Scene.m3qt_bind_weight = bpy.props.FloatProperty(
        name='权重',
        description='绑定选中顶点到新骨骼的权重值',
        default=1.0,
        min=0.0,
        max=1.0,
    )


class M3QT_OT_CreateBone(bpy.types.Operator):
    """创建新的M3骨骼并绑定到父骨骼"""
    bl_idname = 'm3.qt_create_bone'
    bl_label = '创建并绑定骨骼'
    bl_description = '创建新骨骼、绑定父骨骼、初始化M3数据、创建顶点组'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        if not ob:
            return False
        if ob.type == 'ARMATURE':
            return True
        if ob.type == 'MESH' and ob.parent and ob.parent.type == 'ARMATURE':
            return True
        return False

    def execute(self, context):
        scene = context.scene
        bone_name = scene.m3qt_bone_name.strip()
        parent_name = scene.m3qt_parent_bone.strip()
        bone_length = scene.m3qt_bone_length
        at_cursor = scene.m3qt_at_cursor

        if not bone_name:
            self.report({'ERROR'}, '骨骼名称不能为空')
            return {'CANCELLED'}

        # Determine armature
        ob = context.object
        arm_obj = ob if ob.type == 'ARMATURE' else ob.parent

        # Switch to edit mode on armature
        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)

        edit_bones = arm_obj.data.edit_bones

        # Check if bone name already exists
        if bone_name in edit_bones:
            self.report({'ERROR'}, f'骨骼 "{bone_name}" 已存在')
            bpy.ops.object.mode_set(mode='POSE', toggle=False)
            return {'CANCELLED'}

        new_bone = edit_bones.new(bone_name)

        # Determine position
        parent_edit = edit_bones.get(parent_name) if parent_name else None

        if at_cursor:
            head_pos = context.scene.cursor.location.copy()
        elif parent_edit:
            head_pos = parent_edit.tail.copy()
        else:
            head_pos = mathutils.Vector((0, 0, 0))

        new_bone.head = head_pos
        new_bone.tail = head_pos + mathutils.Vector((0, bone_length, 0))

        # Bind to parent bone
        if parent_edit:
            new_bone.parent = parent_edit
            new_bone.use_connect = False

        # Switch to pose mode to initialize M3 data
        bpy.ops.object.mode_set(mode='POSE', toggle=False)

        # Initialize M3 animation hex IDs
        pose_bone = arm_obj.pose.bones.get(bone_name)
        if pose_bone:
            # Trigger lazy initialization via property getter
            _ = pose_bone.m3_location_hex_id
            _ = pose_bone.m3_rotation_hex_id
            _ = pose_bone.m3_scale_hex_id
            _ = pose_bone.m3_batching_hex_id
            # Prevent export culling
            pose_bone.m3_export_cull = False

        # Create vertex groups on child meshes
        vg_count = 0
        if scene.m3qt_create_vgroup:
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            for child in arm_obj.children:
                if child.type != 'MESH':
                    continue
                if not child.vertex_groups.get(bone_name):
                    child.vertex_groups.new(name=bone_name)
                    vg_count += 1
                # Ensure armature modifier
                if not any(m.type == 'ARMATURE' and m.object == arm_obj for m in child.modifiers):
                    mod = child.modifiers.new('Armature', 'ARMATURE')
                    mod.object = arm_obj
            bpy.context.view_layer.objects.active = arm_obj
            bpy.ops.object.mode_set(mode='POSE', toggle=False)

        # Report
        parent_info = f' → 父骨骼: {parent_name}' if parent_name else ' (根骨骼)'
        vg_info = f'，已在 {vg_count} 个网格上创建顶点组' if vg_count > 0 else ''
        self.report({'INFO'}, f'已创建骨骼 "{bone_name}"{parent_info}{vg_info}，M3数据就绪')
        return {'FINISHED'}


class M3QT_OT_ReparentBone(bpy.types.Operator):
    """更改活动骨骼的父骨骼"""
    bl_idname = 'm3.qt_reparent_bone'
    bl_label = '重新绑定父骨骼'
    bl_description = '更改当前活动姿态骨骼的父骨骼'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type == 'ARMATURE'
                and context.object.mode == 'POSE' and context.active_pose_bone)

    def execute(self, context):
        scene = context.scene
        new_parent_name = scene.m3qt_parent_bone.strip()
        arm_obj = context.object
        active_bone_name = context.active_pose_bone.name

        if active_bone_name == new_parent_name:
            self.report({'ERROR'}, '不能将骨骼绑定到自身')
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        edit_bones = arm_obj.data.edit_bones

        bone = edit_bones.get(active_bone_name)
        if not bone:
            bpy.ops.object.mode_set(mode='POSE', toggle=False)
            self.report({'ERROR'}, '未找到骨骼')
            return {'CANCELLED'}

        if new_parent_name:
            new_parent = edit_bones.get(new_parent_name)
            if not new_parent:
                bpy.ops.object.mode_set(mode='POSE', toggle=False)
                self.report({'ERROR'}, f'未找到父骨骼 "{new_parent_name}"')
                return {'CANCELLED'}
            bone.parent = new_parent
        else:
            bone.parent = None

        bone.use_connect = False

        bpy.ops.object.mode_set(mode='POSE', toggle=False)

        parent_info = new_parent_name if new_parent_name else '无 (根骨骼)'
        self.report({'INFO'}, f'"{active_bone_name}" → 父骨骼: {parent_info}')
        return {'FINISHED'}


class M3QT_OT_InitM3Bone(bpy.types.Operator):
    """为活动骨骼初始化M3数据"""
    bl_idname = 'm3.qt_init_m3_bone'
    bl_label = '初始化M3数据'
    bl_description = '为活动骨骼初始化M3动画ID并禁用导出剔除'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object and context.object.type == 'ARMATURE'
                and context.object.mode == 'POSE' and context.active_pose_bone)

    def execute(self, context):
        pb = context.active_pose_bone
        _ = pb.m3_location_hex_id
        _ = pb.m3_rotation_hex_id
        _ = pb.m3_scale_hex_id
        _ = pb.m3_batching_hex_id
        pb.m3_export_cull = False
        self.report({'INFO'}, f'已为 "{pb.name}" 初始化M3数据')
        return {'FINISHED'}


class M3QT_PT_QuickToolsPanel(bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_m3_quick_tools'
    bl_label = 'M3 快捷工具'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'M3'

    @classmethod
    def poll(cls, context):
        ob = context.object
        if not ob:
            return False
        if ob.type == 'ARMATURE':
            return True
        if ob.type == 'MESH' and ob.parent and ob.parent.type == 'ARMATURE':
            return True
        return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ob = context.object
        arm_obj = ob if ob.type == 'ARMATURE' else ob.parent

        # === 创建骨骼 ===
        box = layout.box()
        box.label(text='创建骨骼', icon='BONE_DATA')

        col = box.column(align=True)
        col.prop(scene, 'm3qt_bone_name', text='名称')
        col.prop_search(scene, 'm3qt_parent_bone', arm_obj.data, 'bones', text='父骨骼')
        col.prop(scene, 'm3qt_bone_length', text='长度')
        col.prop(scene, 'm3qt_at_cursor', icon='CURSOR')
        col.prop(scene, 'm3qt_create_vgroup', icon='GROUP_VERTEX')

        row = box.row()
        row.scale_y = 1.5
        row.operator('m3.qt_create_bone', icon='ADD')

        # === 活动骨骼信息 ===
        if ob.type == 'ARMATURE' and ob.mode == 'POSE' and context.active_pose_bone:
            pb = context.active_pose_bone

            box = layout.box()
            box.label(text=f'当前骨骼: {pb.name}', icon='BONE_DATA')

            col = box.column(align=True)
            parent_str = pb.parent.name if pb.parent else '(无 - 根骨骼)'
            col.label(text=f'父骨骼: {parent_str}')
            col.prop(pb, 'm3_export_cull', text='允许导出剔除')
            col.prop(pb, 'm3_batching', text='批处理')

            # 重新绑定父骨骼
            box.separator()
            row = box.row(align=True)
            row.prop_search(scene, 'm3qt_parent_bone', arm_obj.data, 'bones', text='新父骨骼')
            row = box.row()
            row.operator('m3.qt_reparent_bone', icon='LINKED')

            # 初始化M3
            row = box.row()
            row.operator('m3.qt_init_m3_bone', icon='FILE_REFRESH')

            # 动画ID
            row = box.row()
            row.operator('m3.edit_bone_anim_headers', text='编辑动画ID', icon='PREFERENCES')

        # === 自动填充父骨骼提示 ===
        if ob.type == 'ARMATURE' and ob.mode == 'POSE' and context.active_pose_bone:
            if not scene.get('m3qt_parent_bone'):
                box.label(text=f'提示: 活跃骨骼 → {context.active_pose_bone.name}', icon='INFO')


classes = (
    M3QT_OT_CreateBone,
    M3QT_OT_ReparentBone,
    M3QT_OT_InitM3Bone,
    M3QT_PT_QuickToolsPanel,
)
