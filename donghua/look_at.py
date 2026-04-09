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

"""
注视追踪工具 (Look At / Gaze Tracking)

为 M3 模型骨骼提供头部/眼睛追踪目标的能力：
- 创建注视目标 (Empty)
- 为骨骼添加追踪约束 (Damped Track / Track To)
- 影响度控制与实时预览
- 烘焙约束为关键帧 (M3 导出必须)
"""

import bpy
from .anim_tools import get_arm_obj, get_selected_pose_bones


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

CONSTRAINT_NAME = 'M3_LookAt'

TRACK_AXIS_ITEMS = [
    ('TRACK_X', 'X', '骨骼 X 轴指向目标'),
    ('TRACK_NEGATIVE_X', '-X', '骨骼 -X 轴指向目标'),
    ('TRACK_Y', 'Y', '骨骼 Y 轴指向目标（Blender 默认骨骼方向）'),
    ('TRACK_NEGATIVE_Y', '-Y', '骨骼 -Y 轴指向目标'),
    ('TRACK_Z', 'Z', '骨骼 Z 轴指向目标'),
    ('TRACK_NEGATIVE_Z', '-Z', '骨骼 -Z 轴指向目标'),
]

CONSTRAINT_TYPE_ITEMS = [
    ('DAMPED_TRACK', '阻尼追踪', '简单的单轴指向，平滑自然，适合眼球追踪'),
    ('TRACK_TO', '追踪到', '带上轴锁定，可防止翻转，适合头部追踪'),
]

UP_AXIS_ITEMS = [
    ('UP_X', 'X', ''),
    ('UP_Y', 'Y', ''),
    ('UP_Z', 'Z', ''),
]

# SC2 常见的头部/眼球骨骼名称关键词
HEAD_BONE_KEYWORDS = ['head', 'Head', 'HEAD', 'Bone_Head']
EYE_BONE_KEYWORDS = ['eye', 'Eye', 'EYE', 'Bone_Eye']


# ──────────────────────────────────────────────
# 属性注册
# ──────────────────────────────────────────────

def register_props():
    bpy.types.Scene.dh_lookat_target = bpy.props.PointerProperty(
        name='注视目标',
        description='骨骼将追踪注视的目标对象（通常为 Empty）',
        type=bpy.types.Object,
    )
    bpy.types.Scene.dh_lookat_track_axis = bpy.props.EnumProperty(
        name='追踪轴',
        description='骨骼指向目标时使用的轴向',
        items=TRACK_AXIS_ITEMS,
        default='TRACK_Y',
    )
    bpy.types.Scene.dh_lookat_up_axis = bpy.props.EnumProperty(
        name='向上轴',
        description='追踪约束的向上轴（仅 Track To 模式使用）',
        items=UP_AXIS_ITEMS,
        default='UP_Z',
    )
    bpy.types.Scene.dh_lookat_influence = bpy.props.FloatProperty(
        name='影响度',
        description='注视约束的影响强度。0=无影响，1=完全追踪',
        default=1.0,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )
    bpy.types.Scene.dh_lookat_constraint_type = bpy.props.EnumProperty(
        name='约束类型',
        description='使用的追踪约束类型',
        items=CONSTRAINT_TYPE_ITEMS,
        default='DAMPED_TRACK',
    )


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def get_lookat_constraint(pb):
    """获取骨骼上的注视约束（兼容 Blender 自动重命名 M3_LookAt.001 等）"""
    for con in pb.constraints:
        if con.name == CONSTRAINT_NAME or con.name.startswith(CONSTRAINT_NAME + '.'):
            return con
        # 也检查约束类型 + 目标对象名称
        if con.type in {'DAMPED_TRACK', 'TRACK_TO'} and con.name.startswith('M3_'):
            return con
    return None


def get_lookat_bones(arm_obj):
    """获取骨架中所有带有 M3_LookAt 约束的骨骼"""
    result = []
    for pb in arm_obj.pose.bones:
        if get_lookat_constraint(pb):
            result.append(pb)
    return result


def find_head_eye_bones(arm_obj):
    """自动查找可能是头部/眼球的骨骼"""
    candidates = []
    for pb in arm_obj.pose.bones:
        name_lower = pb.name.lower()
        if any(kw.lower() in name_lower for kw in HEAD_BONE_KEYWORDS + EYE_BONE_KEYWORDS):
            candidates.append(pb.name)
    return candidates


# ──────────────────────────────────────────────
# 操作符
# ──────────────────────────────────────────────

class DH_OT_CreateLookAtTarget(bpy.types.Operator):
    """在3D游标位置创建注视目标空对象"""
    bl_idname = 'donghua.create_lookat_target'
    bl_label = '创建注视目标'
    bl_description = '在3D游标位置创建一个 Empty 空对象作为注视目标，可自由移动来控制角色注视方向'
    bl_options = {'UNDO'}

    def execute(self, context):
        arm = get_arm_obj(context)
        if not arm:
            self.report({'ERROR'}, '未找到骨架对象')
            return {'CANCELLED'}

        # 在3D游标处创建 Empty
        target_name = f'{arm.name}_LookAt_Target'

        # 检查是否已存在同名对象
        existing = bpy.data.objects.get(target_name)
        if existing:
            context.scene.dh_lookat_target = existing
            self.report({'INFO'}, f'已复用现有注视目标 "{target_name}"')
            return {'FINISHED'}

        target = bpy.data.objects.new(target_name, None)
        target.empty_display_type = 'SPHERE'
        target.empty_display_size = 0.15
        target.show_name = True

        # 如果有活动骨骼，在其前方创建目标
        if context.active_pose_bone:
            bone = context.active_pose_bone
            bone_head_world = arm.matrix_world @ bone.head
            # 在骨骼前方 2 单位处创建
            forward = arm.matrix_world.to_3x3() @ bone.y_axis
            target.location = bone_head_world + forward.normalized() * 2.0
        else:
            target.location = context.scene.cursor.location.copy()

        # 链接到场景
        context.collection.objects.link(target)

        # 设置为当前目标
        context.scene.dh_lookat_target = target

        self.report({'INFO'}, f'已创建注视目标 "{target.name}"')
        return {'FINISHED'}


class DH_OT_AddLookAt(bpy.types.Operator):
    """为选中骨骼添加注视约束"""
    bl_idname = 'donghua.add_lookat'
    bl_label = '添加注视'
    bl_description = '为选中的姿态骨骼添加追踪约束，使其自动注视目标对象'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return (get_arm_obj(context) is not None
                and context.mode == 'POSE')

    def execute(self, context):
        scene = context.scene
        target = getattr(scene, 'dh_lookat_target', None)
        if not target:
            self.report({'ERROR'}, '请先创建或选择一个注视目标对象')
            return {'CANCELLED'}

        track_axis = scene.dh_lookat_track_axis
        up_axis = scene.dh_lookat_up_axis
        influence = scene.dh_lookat_influence
        constraint_type = scene.dh_lookat_constraint_type

        arm = get_arm_obj(context)
        bones = [pb for pb in arm.pose.bones if pb.bone.select]
        if not bones:
            self.report({'WARNING'}, '没有选中任何骨骼，请先选择')
            return {'CANCELLED'}

        count = 0
        for pb in bones:
            # 如果已存在同名约束就先移除
            existing = pb.constraints.get(CONSTRAINT_NAME)
            if existing:
                pb.constraints.remove(existing)

            # 添加约束
            try:
                if constraint_type == 'DAMPED_TRACK':
                    con = pb.constraints.new('DAMPED_TRACK')
                    con.name = CONSTRAINT_NAME
                    con.target = target
                    con.track_axis = track_axis
                else:  # TRACK_TO
                    # 检查轴冲突: track_axis 和 up_axis 不能在同一方向
                    track_base = track_axis.replace('TRACK_', '').replace('NEGATIVE_', '')
                    up_base = up_axis.replace('UP_', '')
                    if track_base == up_base:
                        # 自动修正: 换一个不冲突的向上轴
                        fallback = {'X': 'UP_Z', 'Y': 'UP_Z', 'Z': 'UP_Y'}
                        up_axis = fallback.get(track_base, 'UP_Z')
                        self.report({'WARNING'}, f'追踪轴和向上轴冲突，已自动修正向上轴为 {up_base}→{up_axis}')

                    con = pb.constraints.new('TRACK_TO')
                    con.name = CONSTRAINT_NAME
                    con.target = target
                    con.track_axis = track_axis
                    con.up_axis = up_axis
                    con.use_target_z = True

                con.influence = influence
                count += 1
            except Exception as e:
                self.report({'ERROR'}, f'骨骼 {pb.name} 约束创建失败: {e}')

        self.report({'INFO'}, f'已为 {count} 个骨骼添加注视约束 → "{target.name}"')
        return {'FINISHED'}


class DH_OT_RemoveLookAt(bpy.types.Operator):
    """移除选中骨骼的注视约束"""
    bl_idname = 'donghua.remove_lookat'
    bl_label = '移除注视'
    bl_description = '移除选中骨骼上的 M3 注视约束（不影响已烘焙的关键帧）'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        arm = get_arm_obj(context)

        # 优先使用选中骨骼
        selected = [pb for pb in arm.pose.bones if pb.bone.select]
        # 过滤出有注视约束的
        bones_with_con = [(pb, get_lookat_constraint(pb)) for pb in selected]
        bones_with_con = [(pb, con) for pb, con in bones_with_con if con is not None]

        # 如果选中骨骼没有约束，回退到所有带约束的骨骼
        if not bones_with_con:
            all_lookat = get_lookat_bones(arm)
            bones_with_con = [(pb, get_lookat_constraint(pb)) for pb in all_lookat]

        if not bones_with_con:
            self.report({'WARNING'}, '没有找到带有注视约束的骨骼')
            return {'CANCELLED'}

        count = 0
        for pb, con in bones_with_con:
            pb.constraints.remove(con)
            count += 1

        self.report({'INFO'}, f'已移除 {count} 个注视约束')
        return {'FINISHED'}


class DH_OT_UpdateLookAtInfluence(bpy.types.Operator):
    """同步更新所有注视约束的影响度"""
    bl_idname = 'donghua.update_lookat_influence'
    bl_label = '同步影响度'
    bl_description = '将当前影响度值同步更新到所有带有注视约束的骨骼'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        influence = context.scene.dh_lookat_influence
        arm = get_arm_obj(context)
        bones = get_lookat_bones(arm)

        if not bones:
            self.report({'WARNING'}, '没有找到带有注视约束的骨骼')
            return {'CANCELLED'}

        for pb in bones:
            con = get_lookat_constraint(pb)
            if con:
                con.influence = influence

        self.report({'INFO'}, f'已将 {len(bones)} 个约束的影响度更新为 {influence:.0%}')
        return {'FINISHED'}


class DH_OT_BakeLookAt(bpy.types.Operator):
    """将注视约束烘焙为关键帧动画（M3 导出前必须执行）"""
    bl_idname = 'donghua.bake_lookat'
    bl_label = '烘焙注视'
    bl_description = '将注视约束烘焙为关键帧动画，然后自动移除约束。M3 格式不支持约束，导出前必须执行此操作'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        if not get_arm_obj(context) or context.mode != 'POSE':
            return False
        arm = get_arm_obj(context)
        return len(get_lookat_bones(arm)) > 0

    def execute(self, context):
        scene = context.scene
        arm = get_arm_obj(context)

        # 收集有注视约束的骨骼
        lookat_bones = get_lookat_bones(arm)
        if not lookat_bones:
            self.report({'WARNING'}, '没有找到带有注视约束的骨骼')
            return {'CANCELLED'}

        # 只选中有约束的骨骼
        for pb in arm.pose.bones:
            pb.bone.select = pb in lookat_bones

        start = scene.frame_start
        end = scene.frame_end

        # 使用 Blender 内置烘焙功能
        try:
            bpy.ops.nla.bake(
                frame_start=start,
                frame_end=end,
                only_selected=True,
                visual_keying=True,
                clear_constraints=True,
                use_current_action=True,
                bake_types={'POSE'},
            )
        except Exception as e:
            self.report({'ERROR'}, f'烘焙失败: {str(e)}')
            return {'CANCELLED'}

        bone_names = ', '.join(pb.name for pb in lookat_bones)
        self.report({'INFO'}, f'已烘焙注视动画 ({start}-{end}帧): {bone_names}')
        return {'FINISHED'}


class DH_OT_SelectLookAtBones(bpy.types.Operator):
    """选择所有带有注视约束的骨骼"""
    bl_idname = 'donghua.select_lookat_bones'
    bl_label = '选择注视骨骼'
    bl_description = '自动选中所有带有 M3 注视约束的骨骼'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        arm = get_arm_obj(context)
        count = 0

        for pb in arm.pose.bones:
            has_lookat = pb.constraints.get(CONSTRAINT_NAME) is not None
            pb.bone.select = has_lookat
            if has_lookat:
                count += 1

        if count:
            self.report({'INFO'}, f'已选中 {count} 个带注视约束的骨骼')
        else:
            self.report({'WARNING'}, '没有找到带有注视约束的骨骼')
        return {'FINISHED'}


class DH_OT_AutoDetectBones(bpy.types.Operator):
    """自动查找并选中可能的头部/眼球骨骼"""
    bl_idname = 'donghua.auto_detect_head_eye'
    bl_label = '自动查找头/眼骨骼'
    bl_description = '根据命名规则自动查找并选中头部和眼球骨骼'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        arm = get_arm_obj(context)
        candidates = find_head_eye_bones(arm)

        if not candidates:
            self.report({'WARNING'}, '未找到头部或眼球骨骼（基于名称匹配: Head, Eye 等）')
            return {'CANCELLED'}

        # 选中找到的骨骼
        for pb in arm.pose.bones:
            pb.bone.select = pb.name in candidates

        self.report({'INFO'}, f'已选中 {len(candidates)} 个候选骨骼: {", ".join(candidates)}')
        return {'FINISHED'}


class DH_OT_KeyLookAtInfluence(bpy.types.Operator):
    """为注视约束的影响度插入关键帧（实现渐入渐出效果）"""
    bl_idname = 'donghua.key_lookat_influence'
    bl_label = '影响度打帧'
    bl_description = '为所有注视约束的影响度属性在当前帧插入关键帧，可制作渐变注视效果'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        if not get_arm_obj(context) or context.mode != 'POSE':
            return False
        arm = get_arm_obj(context)
        return len(get_lookat_bones(arm)) > 0

    def execute(self, context):
        arm = get_arm_obj(context)
        lookat_bones = get_lookat_bones(arm)

        count = 0
        for pb in lookat_bones:
            con = pb.constraints.get(CONSTRAINT_NAME)
            if con:
                # 找到约束在列表中的索引
                con_idx = list(pb.constraints).index(con)
                data_path = f'pose.bones["{pb.name}"].constraints[{con_idx}].influence'
                arm.keyframe_insert(data_path=data_path)
                count += 1

        self.report({'INFO'}, f'已为 {count} 个约束的影响度插入关键帧')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# M3 Turret 快速配置（游戏内实时注视）
# ──────────────────────────────────────────────

TURRET_PRESET_ITEMS = [
    ('WEAPON', '武器炮台', '完整 Yaw+Pitch，大旋转范围，适合武器瞄准'),
    ('LOOKAT', '视觉注视', '小范围 Yaw+Pitch，适合头部/眼球追踪附近单位'),
    ('YAW_ONLY', '仅水平旋转', '只做 Yaw 旋转（如底座），Pitch=0'),
    ('PITCH_ONLY', '仅俯仰', '只做 Pitch 旋转（如炮管），Yaw=0'),
]


class DH_OT_QuickTurretSetup(bpy.types.Operator):
    """为选中骨骼快速创建 M3 Turret（游戏内实时注视/瞄准）"""
    bl_idname = 'donghua.quick_turret_setup'
    bl_label = '快速配置 Turret'
    bl_description = '为选中骨骼一键创建 M3 Turret 数据，用于 SC2 引擎实时注视/瞄准'
    bl_options = {'UNDO'}

    preset: bpy.props.EnumProperty(
        name='预设',
        items=TURRET_PRESET_ITEMS,
        default='WEAPON',
    )

    @classmethod
    def poll(cls, context):
        return get_arm_obj(context) is not None and context.mode == 'POSE'

    def execute(self, context):
        from .. import shared

        arm = get_arm_obj(context)
        bones = [pb for pb in arm.pose.bones if pb.bone.select]
        if not bones:
            self.report({'WARNING'}, '没有选中骨骼')
            return {'CANCELLED'}

        # 确保至少有一个 Turret
        if len(arm.m3_turrets) == 0:
            turret = shared.m3_item_add(arm.m3_turrets)
        else:
            turret = arm.m3_turrets[arm.m3_turrets_index]

        # 查找已用的 group id
        used_groups = {part.group_id for part in turret.parts}
        next_group = max(used_groups, default=0) + 1

        count = 0
        for pb in bones:
            # 检查是否已有 Part 绑定此骨骼
            already_exists = False
            for part in turret.parts:
                if part.bone.value == pb.name:
                    already_exists = True
                    break
            if already_exists:
                self.report({'WARNING'}, f'骨骼 {pb.name} 已有 Turret Part，跳过')
                continue

            part = shared.m3_item_add(turret.parts)
            part.bone.value = pb.name

            if self.preset == 'WEAPON':
                part.group_id = next_group
                part.main_part = True
                part.yaw_weight = 1.0
                part.yaw_limited = True
                part.yaw_min = -3.14159
                part.yaw_max = 3.14159
                part.pitch_weight = 1.0
                part.pitch_limited = True
                part.pitch_min = -0.5236  # -30°
                part.pitch_max = 0.7854   # 45°

            elif self.preset == 'LOOKAT':
                part.group_id = next_group
                part.main_part = True
                part.yaw_weight = 1.0
                part.yaw_limited = True
                part.yaw_min = -0.5236    # -30°
                part.yaw_max = 0.5236     # 30°
                part.pitch_weight = 1.0
                part.pitch_limited = True
                part.pitch_min = -0.2618  # -15°
                part.pitch_max = 0.2618   # 15°

            elif self.preset == 'YAW_ONLY':
                part.group_id = next_group
                part.main_part = True
                part.yaw_weight = 1.0
                part.yaw_limited = True
                part.yaw_min = -3.14159
                part.yaw_max = 3.14159
                part.pitch_weight = 0.0

            elif self.preset == 'PITCH_ONLY':
                part.group_id = next_group
                part.main_part = False
                part.yaw_weight = 0.0
                part.pitch_weight = 1.0
                part.pitch_limited = True
                part.pitch_min = -0.5236  # -30°
                part.pitch_max = 0.7854   # 45°

            next_group += 1
            count += 1

        self.report({'INFO'}, f'已为 {count} 个骨骼创建 Turret Part（预设: {self.preset}）')
        return {'FINISHED'}


class DH_OT_TurretFromSelection(bpy.types.Operator):
    """从选中的多个骨骼创建联动炮台组（底座+炮管）"""
    bl_idname = 'donghua.turret_from_selection'
    bl_label = '多段炮台'
    bl_description = '选中 2 个骨骼 → 第一个做 Yaw 底座，第二个做 Pitch 炮管，同组联动'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        if not get_arm_obj(context) or context.mode != 'POSE':
            return False
        arm = get_arm_obj(context)
        return sum(1 for pb in arm.pose.bones if pb.bone.select) >= 2

    def execute(self, context):
        from .. import shared

        arm = get_arm_obj(context)
        bones = [pb for pb in arm.pose.bones if pb.bone.select]

        if len(bones) < 2:
            self.report({'WARNING'}, '请选中至少 2 个骨骼（底座 + 炮管）')
            return {'CANCELLED'}

        # 确保有 Turret
        if len(arm.m3_turrets) == 0:
            turret = shared.m3_item_add(arm.m3_turrets)
        else:
            turret = arm.m3_turrets[arm.m3_turrets_index]

        used_groups = {part.group_id for part in turret.parts}
        group_id = max(used_groups, default=0) + 1

        # 第一个骨骼 = 底座 (Yaw)
        base_part = shared.m3_item_add(turret.parts)
        base_part.bone.value = bones[0].name
        base_part.group_id = group_id
        base_part.main_part = True
        base_part.yaw_weight = 1.0
        base_part.yaw_limited = True
        base_part.yaw_min = -3.14159
        base_part.yaw_max = 3.14159
        base_part.pitch_weight = 0.0

        # 第二个骨骼 = 炮管 (Pitch)
        gun_part = shared.m3_item_add(turret.parts)
        gun_part.bone.value = bones[1].name
        gun_part.group_id = group_id
        gun_part.main_part = False
        gun_part.yaw_weight = 0.0
        gun_part.pitch_weight = 1.0
        gun_part.pitch_limited = True
        gun_part.pitch_min = -0.5236  # -30°
        gun_part.pitch_max = 0.7854   # 45°

        self.report({'INFO'}, f'已创建联动炮台: 底座={bones[0].name}(Yaw) + 炮管={bones[1].name}(Pitch)，Group={group_id}')
        return {'FINISHED'}


# ──────────────────────────────────────────────
# 类注册列表
# ──────────────────────────────────────────────

classes = (
    DH_OT_CreateLookAtTarget,
    DH_OT_AddLookAt,
    DH_OT_RemoveLookAt,
    DH_OT_UpdateLookAtInfluence,
    DH_OT_BakeLookAt,
    DH_OT_SelectLookAtBones,
    DH_OT_AutoDetectBones,
    DH_OT_KeyLookAtInfluence,
    DH_OT_QuickTurretSetup,
    DH_OT_TurretFromSelection,
)

