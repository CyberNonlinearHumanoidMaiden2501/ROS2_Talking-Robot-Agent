cmake_minimum_required(VERSION 3.8)
project(vr_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/AudioChunk.msg"
  "msg/SpeechSegment.msg"
  "msg/SpeechState.msg"
  "msg/Utterance.msg"
  "srv/Synthesize.srv"
  "srv/ChatFast.srv"
  "srv/ExecuteTool.srv"
  "action/Play.action"
  "action/ReasoningTask.action"
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
