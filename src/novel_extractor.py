import asyncio
import argparse
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')
import re
import logging
import time

try:
    from playwright.async_api import async_playwright
    import pdfplumber
    from deep_translator import GoogleTranslator
except ModuleNotFoundError as exc:
    print(f"Missing Python package: {exc.name}")
    print("Install dependencies from this folder with:")
    print("   setup.bat")
    sys.exit(1)

# Hide harmless font warnings from pdfminer
logging.getLogger("pdfminer").setLevel(logging.ERROR)

STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
    window.chrome = { runtime: {} };
"""

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_DIR, "novel_chapters")
OUTPUT_DIR = DEFAULT_OUTPUT_DIR

# These will be set dynamically in main()
NOVEL_ID = None
BASE_URL = None
START_EPISODE_ID = None
CHAPTER_COUNT = 1
TARGET_LANGUAGE = 'tr'

DEFAULT_BROWSER_PROFILE_DIR = os.path.join(PROJECT_DIR, "browser-profile")
SYSTEM_EDGE_USER_DATA_DIR = (
    os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Edge", "User Data")
    if os.environ.get("LOCALAPPDATA")
    else None
)
EDGE_USER_DATA_DIR = SYSTEM_EDGE_USER_DATA_DIR
EDGE_EXECUTABLE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def parse_start_url(url):
    match = re.search(r'^(https?://[^/]+)/novel/(\d+)/(\d+)', url.strip())
    if not match:
        return None
    return match.group(1), match.group(2), int(match.group(3))


def resolve_path(path):
    return os.path.abspath(os.path.expanduser(path))


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def build_parser():
    parser = argparse.ArgumentParser(
        description="Extract and translate novel chapters from a starting chapter URL."
    )
    parser.add_argument("--url", help="Starting chapter URL, e.g. https://domain/novel/123/456")
    parser.add_argument("--lang", default=None, help="Target language code. Default: tr")
    parser.add_argument("--count", type=positive_int, default=None, help="Number of chapters to download. Default: 1")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Folder for downloaded chapters.")
    parser.add_argument("--profile-dir", default=None, help="Custom Edge/Chromium user data directory.")
    parser.add_argument("--isolated-profile", action="store_true", help="Use ./browser-profile instead of your normal Edge profile.")
    parser.add_argument("--system-edge-profile", action="store_true", help="Use your normal Edge profile. This is the default.")
    parser.add_argument("--edge-executable", default=EDGE_EXECUTABLE, help="Path to Microsoft Edge executable.")
    parser.add_argument("--no-cookie-check", action="store_true", help="Skip the cf_clearance cookie pre-check.")
    return parser


def prompt(message):
    try:
        return input(message).strip()
    except EOFError:
        return ""


def check_edge_executable(edge_executable):
    """Verify the Edge executable path exists."""
    if not edge_executable:
        print("Edge executable path is not configured.")
        print("Use --edge-executable to provide the browser path.")
        return None

    if not os.path.exists(edge_executable):
        alt = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        if os.path.exists(alt):
            return alt
        print(f"Edge not found at '{edge_executable}'.")
        print("Use --edge-executable to provide the browser path.")
        return None
    return edge_executable


async def extract_chapter(context, episode_id, chapter_num):
    """Extract text from a single chapter using print-to-PDF."""

    url = f"{BASE_URL}/novel/{NOVEL_ID}/{episode_id}"
    
    novel_dir = os.path.join(OUTPUT_DIR, NOVEL_ID)
    os.makedirs(novel_dir, exist_ok=True)
    pdf_path = os.path.join(novel_dir, f"chapter_{chapter_num}.pdf")
    tr_txt_path = os.path.join(novel_dir, f"chapter_{chapter_num}_{TARGET_LANGUAGE}.txt")

    if os.path.exists(tr_txt_path):
        print(f"⏭️  Chapter {chapter_num} already extracted and translated, skipping.")
        return "skipped"

    print(f"📥 Processing Chapter {chapter_num}...")

    # Open a new tab inside the persistent Edge context (shares all cookies/session)
    page = await context.new_page()
    await page.add_init_script(STEALTH_SCRIPT)

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)

        # Check if Cloudflare still blocked us
        body_text = await page.inner_text('body')
        if 'Performing security verification' in body_text or 'Ray ID' in body_text:
            print(f"❌ Chapter {chapter_num}: Cloudflare still blocking.")
            print(f"   Make sure you visited {BASE_URL} in Edge and passed verification, then re-run.")
            return "failed"

        viewer = await page.query_selector('.novel-viewer')
        if viewer:
            await page.wait_for_timeout(2000)

        # Print-to-PDF bypasses JS copy protection
        await page.pdf(
            path=pdf_path,
            format='A4',
            margin={'top': '20mm', 'bottom': '20mm', 'left': '15mm', 'right': '15mm'},
            print_background=True
        )

        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, pdf_page in enumerate(pdf.pages):
                page_text = pdf_page.extract_text()
                if page_text:
                    if page_num == 0:
                        lines = page_text.split('\n')
                        nav_lines = [l for l in lines if any(
                            nav in l for nav in ['뉴토끼', '로그인', '목록', '이전화', '다음화']
                        )]
                        if len(nav_lines) > 3:
                            continue
                    text += page_text + "\n\n"

        if not text.strip():
            print(f"⚠️  Chapter {chapter_num}: PDF was blank, will retry next run.")
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            return "failed"

        text = clean_text(text)

        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        print(f"✅ Chapter {chapter_num} extracted ({len(text)} chars)")
        
        tr_text = translate_text(text, TARGET_LANGUAGE)
        tr_text += f"\n\nChapter ID: {episode_id}\n"
        with open(tr_txt_path, 'w', encoding='utf-8') as f:
            f.write(tr_text)
        print(f"✅ Chapter {chapter_num} translated ({len(tr_text)} chars)")

        return "saved"

    except Exception as e:
        print(f"❌ Error on Chapter {chapter_num}: {e}")
        return "failed"
    finally:
        await page.close()


def translate_text(text, target_lang='tr'):
    """Translate text to the target language using deep-translator, chunking to avoid limits."""
    print(f"   Translating to '{target_lang}'...")
    translator = GoogleTranslator(source='auto', target=target_lang)
    paragraphs = text.split('\n')
    translated_paragraphs = []
    
    def translate_chunk(chunk_text):
        for _ in range(3):  # Retry up to 3 times
            try:
                time.sleep(1)  # Rate limit protection
                return translator.translate(chunk_text)
            except Exception as e:
                print(f"      ⚠️ Retrying translation due to error: {e}")
                time.sleep(2)
        print("      ❌ Translation completely failed for this chunk.")
        return chunk_text

    chunk = ""
    for p in paragraphs:
        if len(chunk) + len(p) < 2000:
            chunk += p + "\n"
        else:
            if chunk.strip():
                translated_paragraphs.append(translate_chunk(chunk))
            chunk = p + "\n"
            
    if chunk.strip():
        translated_paragraphs.append(translate_chunk(chunk))
            
    return "\n".join(translated_paragraphs)


def clean_text(text):
    """Remove navigation elements and clean formatting."""
    lines = text.split('\n')
    cleaned = []
    skip_patterns = [
        r'뉴토끼.*무료.*웹툰',
        r'로그인|회원가입|고객센터',
        r'홈\s*[›>]',
        r'목록|이전화|다음화',
        r'글자\s*\d+px',
        r'^\d+/\d+$',
        r'Performing security verification',
        r'Cloudflare|Ray ID',
    ]

    found_content = False
    for line in lines:
        line = line.strip()
        if not line:
            if found_content:
                cleaned.append('')
            continue

        skip = False
        for pattern in skip_patterns:
            if re.search(pattern, line):
                skip = True
                break
        if skip:
            continue

        if len(line) > 10 and not line.startswith('http'):
            found_content = True

        if found_content:
            cleaned.append(line)

    return '\n'.join(cleaned)


async def main():
    global NOVEL_ID, START_EPISODE_ID, CHAPTER_COUNT, BASE_URL, TARGET_LANGUAGE, OUTPUT_DIR, EDGE_USER_DATA_DIR

    args = build_parser().parse_args()
    if not args.url:
        args.url = prompt("Enter the starting chapter URL (e.g., https://example.com/novel/123/456): ")

    parsed_url = parse_start_url(args.url)
    if not parsed_url:
        print("❌ Invalid URL format. Please ensure it matches the pattern: https://domain/novel/ID/EPISODE_ID")
        return

    if not args.lang:
        lang_input = prompt("Enter target language code (e.g., 'tr' for Turkish, 'en' for English) [default: tr]: ")
        args.lang = lang_input if lang_input else 'tr'

    if args.count is None:
        count_input = prompt("How many chapters to download? [default: 1]: ")
        args.count = int(count_input) if count_input.isdigit() and int(count_input) > 0 else 1

    BASE_URL, NOVEL_ID, START_EPISODE_ID = parsed_url
    TARGET_LANGUAGE = args.lang
    CHAPTER_COUNT = args.count
    OUTPUT_DIR = resolve_path(args.output_dir)
    using_system_profile = False
    using_isolated_profile = False
    if args.profile_dir:
        EDGE_USER_DATA_DIR = resolve_path(args.profile_dir)
    elif args.isolated_profile:
        EDGE_USER_DATA_DIR = resolve_path(DEFAULT_BROWSER_PROFILE_DIR)
        using_isolated_profile = True
    else:
        EDGE_USER_DATA_DIR = resolve_path(SYSTEM_EDGE_USER_DATA_DIR) if SYSTEM_EDGE_USER_DATA_DIR else None
        using_system_profile = True

    novel_dir = os.path.join(OUTPUT_DIR, NOVEL_ID)
    os.makedirs(novel_dir, exist_ok=True)

    edge_exe = check_edge_executable(resolve_path(args.edge_executable))
    if not edge_exe:
        return

    if not EDGE_USER_DATA_DIR:
        print("Edge profile folder is not configured.")
        print("Use --profile-dir to provide an Edge or Chromium user data directory.")
        return

    print("Launching Edge with the configured profile (close Edge first if it's open)...")
    print(f"   Profile: {EDGE_USER_DATA_DIR}")
    print(f"   Output:  {novel_dir}")

    stats = {"saved": 0, "skipped": 0, "failed": 0}
    failed_chapters = []

    async with async_playwright() as p:
        # launch_persistent_context opens Edge with the configured profile.
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=EDGE_USER_DATA_DIR,
                executable_path=edge_exe,
                headless=False,  # Run in visible mode to avoid Cloudflare detection
                args=['--disable-blink-features=AutomationControlled'],
                viewport={'width': 1280, 'height': 800},
            )
        except Exception as exc:
            print("Edge closed before Playwright could connect.")
            print(f"Profile: {EDGE_USER_DATA_DIR}")
            print("")
            print("Try these fixes:")
            print("   1. Close every Edge window and background Edge process, then run again.")
            print("   2. Open normal Edge, pass verification, close Edge, then run this script again.")
            print("   3. If the normal profile keeps failing to launch, try --isolated-profile.")
            print("")
            print(f"Original error: {exc}")
            return

        if not args.no_cookie_check:
            cookies = await context.cookies(BASE_URL)
            cf = [c for c in cookies if c['name'] == 'cf_clearance']
            if cf:
                print(f"✅ Profile loaded — site session cookie found.")
            else:
                print(f"⚠️  cf_clearance not found in this browser profile.")
                if using_system_profile:
                    print(f"   Open normal Edge, visit {BASE_URL}, pass verification, close Edge, then re-run.")
                    await context.close()
                    return
                if using_isolated_profile:
                    print("   Isolated profiles often get stuck in verification. Try the default system profile instead.")
                print("   Continuing anyway; the chapter page may fail if blocked.")

        for i in range(CHAPTER_COUNT):
            chapter_num = i + 1
            ep_id = str(START_EPISODE_ID + i)
            status = await extract_chapter(context, ep_id, chapter_num)
            if status in stats:
                stats[status] += 1
            if status == "failed":
                failed_chapters.append((chapter_num, ep_id))
        await context.close()

    failed_file = os.path.join(novel_dir, "failed_chapters.txt")
    if failed_chapters:
        with open(failed_file, 'w', encoding='utf-8') as outfile:
            for chapter_num, episode_id in failed_chapters:
                outfile.write(f"chapter_{chapter_num}: {BASE_URL}/novel/{NOVEL_ID}/{episode_id}\n")
        print(f"⚠️  Failed chapter list saved to '{failed_file}'")
    elif os.path.exists(failed_file):
        os.remove(failed_file)

    # Merge all translated chapters into one file
    all_files = [f for f in os.listdir(novel_dir) if f.startswith("chapter_") and f.endswith(f"_{TARGET_LANGUAGE}.txt")]
    if all_files:
        # Sort numerically by chapter number
        lang_pattern = re.escape(TARGET_LANGUAGE)
        all_files.sort(key=lambda x: int(re.search(rf'chapter_(\d+)_{lang_pattern}', x).group(1)))
        
        merged_file = os.path.join(novel_dir, f"merged_novel_{NOVEL_ID}_{TARGET_LANGUAGE}.txt")
        with open(merged_file, 'w', encoding='utf-8') as outfile:
            for filename in all_files:
                file_path = os.path.join(novel_dir, filename)
                with open(file_path, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())
                    outfile.write("\n\n" + "="*50 + "\n\n")
        print(f"✅ All chapters merged into '{merged_file}'")

    print(f"\nSummary: {stats['saved']} saved, {stats['skipped']} skipped, {stats['failed']} failed")
    print(f"\nDone! Chapters saved to '{novel_dir}'")


if __name__ == "__main__":
    asyncio.run(main())
