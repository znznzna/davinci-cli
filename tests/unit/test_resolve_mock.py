from tests.mocks.resolve_mock import MockProject, MockProjectManager, MockResolve


class TestMockResolve:
    def test_get_version_returns_list(self):
        resolve = MockResolve()
        version = resolve.GetVersion()
        assert isinstance(version, list)
        assert len(version) == 5
        assert version[0] == 20  # major

    def test_get_project_manager_returns_mock(self):
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        assert isinstance(pm, MockProjectManager)

    def test_studio_edition(self):
        resolve = MockResolve(studio=True)
        version = resolve.GetVersion()
        assert "Studio" in version[4]

    def test_free_edition(self):
        resolve = MockResolve(studio=False)
        version = resolve.GetVersion()
        assert version[4] == ""


class TestMockProjectManager:
    def test_get_current_project_returns_mock(self):
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        assert isinstance(project, MockProject)

    def test_get_current_project_returns_none_when_no_project(self):
        resolve = MockResolve(has_project=False)
        pm = resolve.GetProjectManager()
        assert pm.GetCurrentProject() is None

    def test_get_project_list_returns_list(self):
        resolve = MockResolve()
        pm = resolve.GetProjectManager()
        projects = pm.GetProjectListInCurrentFolder()
        assert isinstance(projects, list)


class TestMockProject:
    def test_get_name(self):
        project = MockProject(name="MyProject")
        assert project.GetName() == "MyProject"

    def test_get_timeline_count(self):
        project = MockProject(timeline_count=3)
        assert project.GetTimelineCount() == 3

    def test_get_current_timeline_returns_none_when_no_timeline(self):
        project = MockProject(timeline_count=0)
        assert project.GetCurrentTimeline() is None

    def test_scriptapp_returns_resolve(self):
        """DaVinciResolveScript.scriptapp() のモック"""
        from tests.mocks.resolve_mock import MockDaVinciResolveScript

        dvr = MockDaVinciResolveScript()
        resolve = dvr.scriptapp("Resolve")
        assert isinstance(resolve, MockResolve)
