import os
import click
from dotenv import load_dotenv

from storage import JobCRM
from ai import JobAI
from autofill import autofill_application

# ------------------------------------------------------------------ #
# Bootstrap                                                            #
# ------------------------------------------------------------------ #

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    raise EnvironmentError("GEMINI_API_KEY is not set. Add it to your .env file.")

crm = JobCRM()
ai = JobAI()


# ------------------------------------------------------------------ #
# Shared helpers                                                       #
# ------------------------------------------------------------------ #

def _ensure_company(company_name: str) -> None:
    """Creates a company entry if one doesn't already exist."""
    if crm.company_exists(company_name):
        return

    click.echo(f"  Company '{company_name}' not found. Let's create it.")
    url = click.prompt("  Company website URL")
    try:
        company_info = ai.extract_company_info(url)
        saved = crm.save_company(company_name, company_info)
        click.echo(f"  ✓ Company info saved to {saved}")
    except Exception as e:
        click.echo(f"  ✗ Could not fetch company info: {e}")
        click.echo("  Creating company folder with empty info instead.")
        crm.save_company(company_name, f"# {company_name}\n\nAdd company info here.")


def _ensure_resume(company_name: str, job_title: str, url: str) -> None:
    """Creates a resume entry if one doesn't already exist."""
    _ensure_company(company_name)

    if crm.resume_exists(company_name, job_title):
        return

    if not crm.job_description_exists(company_name, job_title):
        try:
            job_description = ai.extract_job_description(url)
        except Exception as e:
            click.echo(f"✗ Could not fetch job description: {e}", err=True)
            return
    else:
        try:
            job_description = crm.read_job_description(company_name, job_title)
        except FileNotFoundError as e:
            click.echo(f"✗ {e}", err=True)
            return

    try:
        master_resume = crm.read_master("master_resume.md")
    except FileNotFoundError as e:
        click.echo(f"✗ {e}", err=True)
        return

    try:
        resume_template = crm.read_master("resume_template.md")
    except FileNotFoundError as e:
        click.echo(f"✗ {e}", err=True)
        return

    click.echo("  Generating tailored resume...")
    tailored_resume = ai.tailor_resume(
        master_resume=master_resume,
        resume_template=resume_template,
        job_description=job_description,
        job_title=job_title,
        company_name=company_name,
    )

    app_dir = crm.save_application(
        company_name=company_name,
        job_title=job_title,
        url=url,
        job_description=job_description,
        tailored_resume=tailored_resume,
    )
    click.echo(f"✓ Application saved to {app_dir}")
    click.confirm("Please save the .md file to a pdf. Press enter when done", default=True)

    while not crm.resume_pdf_exists(company_name, job_title):
        click.confirm(
            f"\n[!] Missing PDF: Please export the tailored resume for {job_title} to PDF.\n"
            f"Press Enter once the PDF is ready...",
            default=True,
        )


# ------------------------------------------------------------------ #
# Commands                                                             #
# ------------------------------------------------------------------ #

@click.group()
def cli() -> None:
    """Job Search CRM — manage applications, resumes, and outreach."""
    pass


@cli.command("add-company")
@click.argument("company_name")
@click.argument("url")
def add_company(company_name: str, url: str) -> None:
    """Create a company listing from their website URL.

    Example: python main.py add-company Stripe https://stripe.com
    """
    if crm.company_exists(company_name):
        click.echo(f"Company '{company_name}' already exists. Skipping.")
        return

    click.echo(f"Fetching info for {company_name}...")
    try:
        company_info = ai.extract_company_info(url)
        saved = crm.save_company(company_name, company_info)
        click.echo(f"✓ Saved company info to {saved}")
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)


@cli.command("create-resume")
@click.argument("company_name")
@click.argument("job_title")
@click.argument("url")
def create_resume(company_name: str, job_title: str, url: str) -> None:
    """Add a resume for a job application.

    Creates the company entry first if it doesn't exist yet.

    Example: python main.py create-resume Stripe "Backend Engineer" https://stripe.com/jobs/123
    """
    click.echo(f"Processing application for {job_title} at {company_name}...")

    if crm.resume_exists(company_name, job_title):
        click.echo("Resume already exists. Skipping.")
        return

    _ensure_resume(company_name, job_title, url)


@cli.command("apply")
@click.argument("company_name")
@click.argument("job_title")
@click.argument("url")
def apply(company_name: str, job_title: str, url: str) -> None:
    """Apply to a job — creates company/resume if needed, then autofills the form.

    Example: python main.py apply Stripe "Backend Engineer" https://stripe.com/jobs/123
    """
    click.echo(f"Processing application for {job_title} at {company_name}...")

    _ensure_resume(company_name, job_title, url)

    click.echo(f"Opening application at {url}...")
    resume_path = str(crm.get_resume_path(company_name, job_title))
    profile = crm.read_master("profiles.json")

    autofill_application(url, profile, resume_path)


@cli.command("status")
@click.option(
    "--filter", "status_filter", default=None,
    help="Show only: applied, interviewing, offer, rejected, withdrawn",
)
def show_status(status_filter: str | None) -> None:
    """Show a dashboard of all applications and their current status.

    Example: python main.py status
             python main.py status --filter interviewing
    """
    apps = crm.get_all_applications()

    if not apps:
        click.echo("No applications found. Run 'apply' or 'create-resume' to get started.")
        return

    if status_filter:
        apps = [a for a in apps if a["status"] == status_filter.lower()]
        if not apps:
            click.echo(f"No applications with status '{status_filter}'.")
            return

    STATUS_STYLES = {
        "applied":      ("cyan",   "⏳"),
        "interviewing": ("yellow", "🎙 "),
        "offer":        ("green",  "🎉"),
        "rejected":     ("red",    "✗ "),
        "withdrawn":    ("white",  "–  "),
    }

    totals: dict[str, int] = {}
    for a in apps:
        totals[a["status"]] = totals.get(a["status"], 0) + 1

    click.echo("")
    click.echo(click.style("  JOB SEARCH DASHBOARD  ", fg="white", bg="blue", bold=True))
    click.echo("")

    current_company = None
    for a in sorted(apps, key=lambda x: (x["company"].lower(), x["applied_date"])):
        if a["company"] != current_company:
            current_company = a["company"]
            click.echo(click.style(f"  {current_company}", bold=True))

        color, icon = STATUS_STYLES.get(a["status"], ("white", "? "))
        status_label = click.style(f"[{a['status'].upper():<12}]", fg=color)
        date_label   = click.style(a["applied_date"], dim=True)
        click.echo(f"    {icon} {status_label}  {a['title']:<40}  {date_label}")

    click.echo("")
    summary_parts = [
        click.style(f"{v} {k}", fg=STATUS_STYLES.get(k, ("white",))[0])
        for k, v in totals.items()
    ]
    click.echo("  " + "  |  ".join(summary_parts))
    click.echo("")


@cli.command("update-status")
@click.argument("company_name")
@click.argument("job_title")
@click.argument(
    "new_status",
    metavar="STATUS",
    type=click.Choice(
        ["applied", "interviewing", "offer", "rejected", "withdrawn"],
        case_sensitive=False,
    ),
)
def update_status(company_name: str, job_title: str, new_status: str) -> None:
    """Update the pipeline status of an application.

    STATUS: applied | interviewing | offer | rejected | withdrawn

    Example: python main.py update-status Stripe "Backend Engineer" interviewing
    """
    try:
        crm.update_application_status(company_name, job_title, new_status)
        click.echo(f"✓ {job_title} @ {company_name}  →  {new_status.upper()}")
    except FileNotFoundError as e:
        click.echo(f"✗ {e}", err=True)


@cli.command("email")
@click.argument("company_name")
@click.argument("person_name")
def email(company_name: str, person_name: str) -> None:
    """Draft an outreach email to a person at a company.

    Example: python main.py email Stripe "Jane Smith"
    """
    _ensure_company(company_name)

    templates = crm.list_email_templates()
    if not templates:
        click.echo(
            "✗ No email templates found in Job-Search/masters/. "
            "Add a .md template file first.",
            err=True,
        )
        return

    click.echo("Available email templates:")
    for i, name in enumerate(templates, start=1):
        click.echo(f"  {i}. {name}")

    template_choice = click.prompt("Choose a template by number", type=int)
    if not 1 <= template_choice <= len(templates):
        click.echo("✗ Invalid choice.", err=True)
        return

    template_filename = templates[template_choice - 1]

    try:
        template = crm.read_master(template_filename)
    except FileNotFoundError as e:
        click.echo(f"✗ {e}", err=True)
        return

    context_notes = crm.read_person_context(company_name, person_name)
    if context_notes:
        click.echo(f"  Found existing context notes for {person_name}.")
    else:
        click.echo(f"  No existing context for {person_name}.")
        context_notes = click.prompt(
            "  Add any context notes (LinkedIn bio snippet, how you met, etc.) "
            "or press Enter to skip",
            default="",
        )

    click.echo(f"  Drafting email to {person_name}...")
    draft = ai.draft_email(
        template=template,
        person_name=person_name,
        company_name=company_name,
        context_notes=context_notes,
    )

    saved = crm.save_email_draft(company_name, person_name, draft)
    click.echo(f"✓ Email draft saved to {saved}")


@cli.command("tasks")
def show_tasks() -> None:
    """Scan all contacts and identify pending outreach tasks."""
    pending = crm.get_pending_tasks()

    if not pending:
        click.echo("☀️  No pending tasks! You're all caught up.")
        return

    for task in pending:
        click.echo(
            f"\n[{task['type'].upper()}] {task['person']} @ {task['company']} "
            f"({task['days_ago']} day(s) ago)"
        )

        if not click.confirm(f"  Draft {task['type'].replace('_', ' ')} for {task['person']}?"):
            continue

        template_filename = f"{task['type']}.md"
        try:
            template = crm.read_master(template_filename)
        except FileNotFoundError:
            click.echo(
                f"  ✗ No template found for '{task['type']}'. "
                f"Add {template_filename} to Job-Search/masters/ and re-run.",
                err=True,
            )
            continue

        draft = ai.draft_email(
            template=template,
            person_name=task["person"],
            company_name=task["company"],
            context_notes=crm.read_person_context(task["company"], task["person"]),
        )

        edited_draft = click.edit(draft)
        if edited_draft is None:
            click.echo("  (No changes made — using original draft.)")
            edited_draft = draft

        if click.confirm("  Mark as sent and update logs?"):
            crm.save_person(task["company"], task["person"], context="")
            crm.update_interaction_log(
                task["company"],
                task["person"],
                task["type"],
                edited_draft,
            )
            click.echo("  ✓ Log updated.")


# ------------------------------------------------------------------ #
# Entrypoint                                                           #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    cli()