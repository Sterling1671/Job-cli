from pathlib import Path
from datetime import date


class JobCRM:
    """Handles all file system operations for the job search CRM."""

    def __init__(self, root_dir: str = "Job-Search") -> None:
        self.root = Path(root_dir)
        self.masters: Path = self.root / "masters"
        self.companies: Path = self.root / "companies"
        self._ensure_dirs([self.masters, self.companies])
        self._seed_masters()

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _ensure_dirs(self, paths: list[Path]) -> None:
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)

    def _seed_masters(self) -> None:
        """Create placeholder master files if they don't exist yet."""
        placeholders = {
            "master_resume.md": "# Master Resume\nAdd your full resume content here.",
            "cold_outreach.md": "# Cold Outreach Template\nWrite your outreach template here.",
            "follow_up.md": "# Follow-Up Template\nWrite your follow-up template here.",
        }
        for filename, content in placeholders.items():
            path = self.masters / filename
            if not path.exists():
                path.write_text(content)

    # ------------------------------------------------------------------ #
    # Read helpers                                                         #
    # ------------------------------------------------------------------ #

    def read_master(self, filename: str) -> str:
        path = self.masters / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Master file '{filename}' not found in {self.masters}. "
                "Create it before running this command."
            )
        return path.read_text()

    def company_exists(self, company_name: str) -> bool:
        return (self.companies / company_name).exists()

    def person_exists(self, company_name: str, person_name: str) -> bool:
        return self._person_dir(company_name, person_name).exists()

    def read_person_context(self, company_name: str, person_name: str) -> str:
        context_file = self._person_dir(company_name, person_name) / "context.md"
        if context_file.exists():
            return context_file.read_text()
        return ""

    def list_email_templates(self) -> list[str]:
        return [f.name for f in self.masters.iterdir() if f.suffix == ".md" and f.name != "master_resume.md"]

    # ------------------------------------------------------------------ #
    # Path builders                                                        #
    # ------------------------------------------------------------------ #

    def _company_dir(self, company_name: str) -> Path:
        return self.companies / company_name

    def _app_dir(self, company_name: str, job_title: str) -> Path:
        return self._company_dir(company_name) / "applications" / job_title.replace(" ", "_")

    def _person_dir(self, company_name: str, person_name: str) -> Path:
        return self._company_dir(company_name) / "people" / person_name.replace(" ", "_")

    # ------------------------------------------------------------------ #
    # Write operations                                                     #
    # ------------------------------------------------------------------ #

    def save_company(self, company_name: str, company_info: str) -> Path:
        company_dir = self._company_dir(company_name)
        (company_dir / "applications").mkdir(parents=True, exist_ok=True)
        (company_dir / "people").mkdir(parents=True, exist_ok=True)
        info_file = company_dir / "company_info.md"
        info_file.write_text(company_info)
        return info_file

    def save_application(
        self,
        company_name: str,
        job_title: str,
        url: str,
        job_description: str,
        tailored_resume: str,
    ) -> Path:
        app_dir = self._app_dir(company_name, job_title)
        app_dir.mkdir(parents=True, exist_ok=True)

        today = date.today().strftime("%B %d, %Y")
        job_data = f"# {job_title}\n\n## Status: Applied on {today}\n\n**URL:** {url}\n\n**Description:**\n{job_description}"
        (app_dir / "job_description.md").write_text(job_data)
        (app_dir / "tailored_resume.md").write_text(tailored_resume)
        return app_dir

    def save_email_draft(
        self,
        company_name: str,
        person_name: str,
        draft: str,
    ) -> Path:
        person_dir = self._person_dir(company_name, person_name)
        person_dir.mkdir(parents=True, exist_ok=True)

        # Seed an empty context file if this is a new person
        context_file = person_dir / "context.md"
        if not context_file.exists():
            context_file.write_text(f"# Notes on {person_name}\nAdd context here.")

        draft_file = person_dir / "draft_email.md"
        draft_file.write_text(draft)
        return draft_file
