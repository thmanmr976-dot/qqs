import Quickshell
import QtQuick

ShellRoot {
    PanelWindow {
        anchors { top: true; left: true; right: true }
        implicitHeight: 38
        color: "#182231"
        Text {
            anchors.centerIn: parent
            text: "qqs • Hello Hyprland"
            color: "#8fe7cd"
            font.pixelSize: 16
        }
    }
}
