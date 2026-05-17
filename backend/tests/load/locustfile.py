"""Load testing for Revis.io API. Run with: locust -f backend/tests/load/locustfile.py"""

from locust import HttpUser, between, task


class Revis.ioUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Register and login at start of test."""
        pass

    @task(3)
    def view_dashboard(self):
        """Simulate client viewing dashboard."""
        pass

    @task(2)
    def list_files(self):
        """Simulate client listing project files."""
        pass

    @task(1)
    def view_project(self):
        """Simulate viewing project details."""
        pass