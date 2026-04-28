from pathlib import Path
from datetime import date, datetime
import os
import yaml
import frontmatter


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
            "resume_template.md": "# Resume Template\nAdd your resume template here.",
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

    def resume_exists(self, company_name: str, job_title: str) -> bool:
        app_file = self._app_dir(company_name, job_title) / "tailored_resume.md"
        return app_file.exists()
    
    def resume_pdf_exists(self, company_name: str, job_title: str) -> bool:
        app_file = self._app_dir(company_name, job_title) / "tailored_resume.pdf"
        return app_file.exists()

    def job_description_exists(self, company_name: str, job_title: str) -> bool:
        app_file = self._app_dir(company_name, job_title) / "job_description.md"
        return app_file.exists()

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
        return self.companies / company_name.replace(" ", "_")

    def _app_dir(self, company_name: str, job_title: str) -> Path:
        return self._company_dir(company_name) / "applications" / job_title.replace(" ", "_")

    def _person_dir(self, company_name: str, person_name: str) -> Path:
        return self._company_dir(company_name) / "people" / person_name.replace(" ", "_")

    # ------------------------------------------------------------------ #
    # Path Gets                                                            #
    # ------------------------------------------------------------------ #
    def get_resume_path(self, company_name: str, job_title: str) -> Path:
        return self._app_dir(company_name, job_title) / "tailored_resume.pdf"

    def get_log_path(self, company_name: str, person_name: str) -> Path:
        return self._person_dir(company_name, person_name) / "interaction_log.md"

    def read_job_description(self, company_name: str, job_title: str) -> str:
        path = self._app_dir(company_name, job_title) / "job_description.md"
        if not path.exists():
            raise FileNotFoundError(
                f"{str(path)} not found."
            )
        return path.read_text()
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

    def save_person(
        self,
        company_name: str,
        person_name: str,
        context: str,
    ) -> Path:
        person_dir = self._person_dir(company_name, person_name)
        person_dir.mkdir(parents=True, exist_ok=True)

        # Seed an empty context file if this is a new person
        context_file = person_dir / "context.md"
        if not context_file.exists():
            context_file.write_text(f"# Notes on {person_name}\n{context}")

        return context_file


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

    def update_interaction_log(self, company: str, person: str, interaction_type: str, content: str):
        """Updates metadata and appends the email content to the log file."""
        log_path = self._get_log_path(company, person)
        today = date.today().isoformat()

        # Load existing post or create a new one
        if log_path.exists():
            post = frontmatter.load(log_path)
        else:
            post = frontmatter.Post("")

        # Update metadata
        post['last_contact_date'] = today
        post['last_contact_type'] = interaction_type
        
        # Append to the body
        new_entry = f"\n\n## {today} - {interaction_type.replace('_', ' ').title()}\n\n{content}\n"
        post.content += new_entry

        # Save back to file
        with open(log_path, 'wb') as f:
            frontmatter.dump(post, f)

    def get_pending_tasks(self):
        """Scans all people folders and returns tasks based on timing logic."""
        tasks = []
        today = date.today()
        people_dir = self.base_path / "companies"
        
        # Walk through companies/*/people/*
        for log_file in people_dir.glob("**/people/*/interaction_log.md"):
            post = frontmatter.load(log_file)
            
            # Extract basic info from path and frontmatter
            person_name = log_file.parent.name.replace("_", " ")
            company_name = log_file.parent.parent.parent.name.replace("_", " ")
            
            last_date_str = post.get('last_contact_date')
            last_type = post.get('last_contact_type')

            if not last_date_str:
                continue

            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            days_since = (today - last_date).days

            # Logic Engine
            task_type = None

            # 1. Check for 3-day follow up after cold outreach
            if last_type == "cold_outreach" and days_since >= 3:
                task_type = "follow_up"

            # 2. Check for Thank You (if status was 'interview' but no thank you sent)
            elif last_type == "interview" and days_since >= 0:
                task_type = "thank_you"

            # 3. Monthly Check-in logic
            # (If it's been 30 days since ANY interaction)
            elif days_since >= 30:
                task_type = "monthly_checkin"

            if task_type:
                tasks.append({
                    "person": person_name,
                    "company": company_name,
                    "type": task_type,
                    "days_ago": days_since
                })
        
        return tasks