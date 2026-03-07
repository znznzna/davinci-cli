"""DaVinci Resolve Python API の軽量モック実装。

実際の DaVinci Resolve や DaVinciResolveScript が不要な状態で
unit test を実行できるようにするための純粋 Python 実装。

API正確性に関する注意:
  このモックは DaVinci Resolve 19.x の Python API を参考に作成している。
  GetVersion() は dict を返す設計としているが、実際の API レスポンスと
  フィールド名・型が異なる可能性がある。新しいバージョンの DaVinci Resolve で
  テストする際は、まず実 API の戻り値を確認し、モックを更新すること。

使用例:
    from tests.mocks.resolve_mock import MockDaVinciResolveScript
    dvr = MockDaVinciResolveScript()
    resolve = dvr.scriptapp("Resolve")
"""

from __future__ import annotations

from typing import Any


class MockTimeline:
    """タイムラインのモック。"""

    def __init__(self, name: str = "Timeline 1") -> None:
        self._name = name

    def GetName(self) -> str:
        return self._name

    def GetStartFrame(self) -> int:
        return 0

    def GetEndFrame(self) -> int:
        return 240

    def GetTrackCount(self, track_type: str) -> int:
        return 2

    def GetSetting(self, key: str) -> str:
        _defaults: dict[str, str] = {
            "timelineFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }
        return _defaults.get(key, "")

    def GetStartTimecode(self) -> str:
        return "00:00:00:00"


class MockProject:
    """プロジェクトのモック。"""

    def __init__(
        self,
        name: str = "Untitled Project",
        timeline_count: int = 1,
    ) -> None:
        self._name = name
        self._timeline_count = timeline_count
        self._timelines = [MockTimeline(f"Timeline {i + 1}") for i in range(timeline_count)]

    def GetName(self) -> str:
        return self._name

    def GetTimelineCount(self) -> int:
        return self._timeline_count

    def GetCurrentTimeline(self) -> MockTimeline | None:
        if not self._timelines:
            return None
        return self._timelines[0]

    def GetTimelineByIndex(self, index: int) -> MockTimeline | None:
        try:
            return self._timelines[index - 1]  # DaVinci API は 1-indexed
        except IndexError:
            return None

    def GetSetting(self, key: str) -> str:
        _defaults: dict[str, str] = {
            "timelineFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }
        return _defaults.get(key, "")


class MockProjectManager:
    """プロジェクトマネージャーのモック。"""

    def __init__(
        self,
        has_project: bool = True,
        project_name: str = "Untitled Project",
    ) -> None:
        self._current_project = MockProject(project_name) if has_project else None
        self._project_names = [project_name] if has_project else []

    def GetCurrentProject(self) -> MockProject | None:
        return self._current_project

    def GetProjectListInCurrentFolder(self) -> list[str]:
        return list(self._project_names)

    def CreateProject(self, name: str) -> MockProject | None:
        project = MockProject(name)
        self._project_names.append(name)
        return project


class MockResolve:
    """DaVinci Resolve アプリケーションオブジェクトのモック。"""

    def __init__(
        self,
        studio: bool = False,
        has_project: bool = True,
        project_name: str = "Untitled Project",
    ) -> None:
        self._studio = studio
        self._project_manager = MockProjectManager(
            has_project=has_project,
            project_name=project_name,
        )

    def GetVersion(self) -> dict[str, Any]:
        product = "DaVinci Resolve Studio" if self._studio else "DaVinci Resolve"
        return {
            "product": product,
            "major": 19,
            "minor": 0,
            "patch": 0,
            "build": 0,
            "suffix": "",
        }

    def GetVersionString(self) -> str:
        product = "DaVinci Resolve Studio" if self._studio else "DaVinci Resolve"
        return f"{product} 19.0.0b0"

    def GetProjectManager(self) -> MockProjectManager:
        return self._project_manager

    def OpenPage(self, page_name: str) -> bool:
        valid_pages = {
            "media",
            "cut",
            "edit",
            "fusion",
            "color",
            "fairlight",
            "deliver",
        }
        return page_name in valid_pages

    def GetCurrentPage(self) -> str:
        return "edit"

    def Quit(self) -> None:
        pass


class MockDaVinciResolveScript:
    """DaVinciResolveScript モジュールのモック。

    テスト内で以下のようにパッチして使用する:
        with patch("davinci_cli.core.connection._import_resolve_script",
                   return_value=MockDaVinciResolveScript()):
            resolve = get_resolve()
    """

    def __init__(self, studio: bool = False, has_project: bool = True) -> None:
        self._resolve = MockResolve(studio=studio, has_project=has_project)

    def scriptapp(self, app_name: str) -> MockResolve | None:
        if app_name == "Resolve":
            return self._resolve
        return None
