import random
import re

from genanki import Model, Deck, Note, Package
from markdown import markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name, PythonLexer, JavascriptLexer
from pygments.formatters import HtmlFormatter

from database import Problem, Submission
from utils import parser as conf


def random_id():
    return random.randrange(1 << 30, 1 << 31)


def markdown_to_html(content: str):
    # replace the math symbol "$$x$$" to "\(x\)" to make it compatible with mathjax
    content = re.sub(
        pattern=r"\$\$(.*?)\$\$",
        repl=r"\(\1\)",
        string=content
    )

    # also need to load the mathjax and toc extensions
    return markdown(content, extensions=['mdx_math', 'toc', 'fenced_code', 'tables'])


def code_to_html(source, language):
    """Convert code to HTML with syntax highlighting using Pygments"""
    # Map LeetCode language names to Pygments lexer names
    language_map = {
        'python': 'python',
        'python3': 'python',
        'javascript': 'javascript',
        'js': 'javascript',
        'java': 'java',
        'cpp': 'cpp',
        'c++': 'cpp',
        'c': 'c',
        'csharp': 'csharp',
        'c#': 'csharp',
        'ruby': 'ruby',
        'swift': 'swift',
        'golang': 'go',
        'go': 'go',
        'kotlin': 'kotlin',
        'rust': 'rust',
        'typescript': 'typescript',
        'php': 'php',
        'scala': 'scala',
        'mysql': 'sql',
        'mssql': 'sql',
        'oraclesql': 'sql'
    }
    
    # Get the appropriate lexer
    lexer_name = language_map.get(language.lower(), 'python')
    try:
        lexer = get_lexer_by_name(lexer_name)
    except:
        lexer = PythonLexer()
    
    # Use HtmlFormatter with appropriate options for Anki
    formatter = HtmlFormatter(
        style='default',
        noclasses=False,
        cssclass='highlight',
        linenos=False
    )
    
    return highlight(source, lexer, formatter)


def get_anki_model():
    with open(conf.get("Anki", "front"), 'r') as f:
        front_template = f.read()
    with open(conf.get("Anki", 'back'), 'r') as f:
        back_template = f.read()
    with open(conf.get("Anki", 'css'), 'r') as f:
        css = f.read()

    anki_model = Model(
        model_id=1048217874,
        name="LeetCode",
        fields=[
            {"name": "ID"},
            {"name": "Title"},
            {"name": "TitleSlug"},
            {"name": "Difficulty"},
            {"name": "Description"},
            {"name": "Tags"},
            {"name": "TagSlugs"},
            {"name": "Solution"},
            {"name": "Submission"}
        ],
        templates=[
            {
                "name": "LeetCode",
                "qfmt": front_template,
                "afmt": back_template
            }
        ],
        css=css
    )
    return anki_model


def make_note(problem):
    print(f"📓 Producing note for problem: {problem.title}...")
    tags = ";".join([t.name for t in problem.tags])
    tags_slug = ";".join([t.slug for t in problem.tags])

    # Get the latest submission only (sorted by created date)
    submission_html = ""
    try:
        latest_submission = (
            Submission.select()
            .where(Submission.slug == problem.slug)
            .order_by(Submission.created.desc())
            .first()
        )
        
        if latest_submission:
            # Decode unicode escapes in the source code
            source = re.sub(
                r'(\\u[\s\S]{4})',
                lambda x: x.group(1).encode("utf-8").decode("unicode-escape"),
                latest_submission.source
            )
            # Add language label before the code
            language_label = f'<div style="margin-bottom: 5px; color: #666; font-weight: bold;">Language: {latest_submission.language.title()}</div>'
            submission_html = language_label + code_to_html(source, latest_submission.language)
    except Exception as e:
        print(f"    ⚠️  No submission found: {e}")
        submission_html = "<p>No submission available</p>"

    note = Note(
        model=get_anki_model(),
        fields=[
            str(problem.display_id),
            problem.title,
            problem.slug,
            problem.level,
            problem.description,
            tags,
            tags_slug,
            "",  # Empty solution field - we only show submission now
            submission_html
        ],
        guid=str(problem.display_id),
        sort_field=str(problem.display_id),
        tags=[t.slug for t in problem.tags]
    )
    return note


def render_anki():
    problems = Problem.select().order_by(
        Problem.display_id
    )

    anki_deck = Deck(
        deck_id=random_id(),
        name="LeetCode"
    )

    for problem in problems:
        note = make_note(problem)
        anki_deck.add_note(note)

    path = conf.get("Anki", "output")
    Package(anki_deck).write_to_file(path)


if __name__ == '__main__':
    render_anki()
