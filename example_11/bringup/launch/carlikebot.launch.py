# Copyright 2020 ros2_control Development Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, RegisterEventHandler
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command, FindExecutable, PathJoinSubstitution, LaunchConfiguration

from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Declare arguments
    declared_arguments = []
    declared_arguments.append(
        DeclareLaunchArgument(
            "gui",
            default_value="true",
            description="Start RViz2 automatically with this launch file.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "remap_odometry_tf",
            default_value="false",
            description="Remap odometry TF from the steering controller to the TF tree.",
        )
    )

    # Initialize Arguments
    gui = LaunchConfiguration("gui")
    remap_odometry_tf = LaunchConfiguration("remap_odometry_tf")

    # Get URDF via xacro
    robot_description_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            PathJoinSubstitution(
                [FindPackageShare("ros2_control_demo_example_11"), "urdf", "carlikebot.urdf.xacro"]
            ),
        ]
    )
    robot_description = {"robot_description": robot_description_content}

    ros2_control_yaml_file = PathJoinSubstitution(
        [
            FindPackageShare("ros2_control_demo_example_11"),
            "config",
            "carlikebot_controllers.yaml",
        ]
    )
    rviz_config_file = PathJoinSubstitution(
        [
            FindPackageShare("ros2_control_demo_description"),
            "carlikebot/rviz",
            "carlikebot.rviz",
        ]
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="both",
        parameters=[robot_description],
    )

    # 启动 controller manager + 拉起 joint_state_broadcaster
    control_node = Node(
        package="controller_manager",
        executable="ros2_control_node",  # 执行后节点名称是 controller_manager
        parameters=[ros2_control_yaml_file],  # 只会去看 yaml 文件的 controller_manager 块
        output="both",
    )
    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster"],  # 去让Controller Manager 加载（拉起）之前登记的这一个Controller 的名字。
    )

    # Delay rviz start after `joint_state_broadcaster`
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="log",
        arguments=["-d", rviz_config_file],
        condition=IfCondition(gui),
    )
    delay_rviz_after_joint_state_broadcaster_spawner = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[rviz_node],
        )
    )

    # Delay start of robot_controller after `joint_state_broadcaster`
    # the steering controller libraries by default publish odometry on a separate topic than /tf
    robot_bicycle_controller_spawner_remapped = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "bicycle_steering_controller",  # controller_names (要操作的controller)
            "--param-file", ros2_control_yaml_file,  # --param-file (给这个 controller 加载参数文件)
            "--controller-ros-args", "-r /bicycle_steering_controller/tf_odometry:=/tf",  # 在 spawner 启动 controller 时，把一串 ROS CLI 参数原样传给这个 controller 节点
        ],
        condition=IfCondition(remap_odometry_tf),
    )
    robot_bicycle_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "bicycle_steering_controller",
            "--param-file", ros2_control_yaml_file
        ],
        condition=UnlessCondition(remap_odometry_tf),
    )
    delay_robot_controller_spawner_after_joint_state_broadcaster_spawner = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[robot_bicycle_controller_spawner_remapped, robot_bicycle_controller_spawner],
        )
    )

    nodes = [
        robot_state_publisher,

        control_node,
        joint_state_broadcaster_spawner,

        delay_rviz_after_joint_state_broadcaster_spawner,

        delay_robot_controller_spawner_after_joint_state_broadcaster_spawner,
    ]

    return LaunchDescription(declared_arguments + nodes)
