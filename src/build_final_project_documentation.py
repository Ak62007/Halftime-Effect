"""Build the final Word documentation for The Halftime Effect project."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/word/The_Halftime_Effect_Final_Project_Documentation.docx"

NAVY = "183A5A"
BLUE = "2B73D6"
PALE_BLUE = "EAF2F8"
PALE_GRAY = "F5F7F9"
BORDER = "D9D9D9"
GRAY = RGBColor(91, 104, 118)


def set_font(run, size: float | None = None, name: str = "Arial") -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    if size is not None:
        run.font.size = Pt(size)


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("Page ")
    set_font(run, 8.5)
    run.font.color.rgb = GRAY
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, end])


def remove_paragraph_border(style) -> None:
    ppr = style._element.get_or_add_pPr()
    border = ppr.find(qn("w:pBdr"))
    if border is not None:
        ppr.remove(border)


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.78)
    section.right_margin = Inches(0.78)
    section.header_distance = Inches(0.3)
    section.footer_distance = Inches(0.28)

    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.line_spacing = 1.12
    normal.paragraph_format.space_after = Pt(6)

    title = doc.styles["Title"]
    title.font.name = "Arial"
    title._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    title._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    title.font.size = Pt(26)
    title.font.bold = True
    title.font.color.rgb = RGBColor(0, 0, 0)
    title.paragraph_format.space_after = Pt(10)
    remove_paragraph_border(title)

    for style_name, size, before, after in (
        ("Heading 1", 16, 12, 6),
        ("Heading 2", 13, 9, 4),
        ("Heading 3", 11.5, 7, 3),
    ):
        style = doc.styles[style_name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
        remove_paragraph_border(style)

    caption = doc.styles["Caption"]
    caption.font.name = "Arial"
    caption._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    caption._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    caption.font.size = Pt(9)
    caption.font.italic = True
    caption.font.color.rgb = GRAY
    caption.paragraph_format.space_before = Pt(3)
    caption.paragraph_format.space_after = Pt(8)
    caption.paragraph_format.keep_with_next = False

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = header.add_run("THE HALFTIME EFFECT  |  FINAL PROJECT DOCUMENTATION")
    set_font(run, 8.5)
    run.bold = True
    run.font.color.rgb = GRAY

    add_page_number(section.footer.paragraphs[0])

    props = doc.core_properties
    props.title = "The Halftime Effect Final Project Documentation"
    props.subject = "Forecasting Great Britain electricity demand around England football matches"
    props.author = "The Halftime Effect project team"
    props.keywords = "electricity demand, time series, football, forecasting, ARX, Ridge, ARMA"


def add_text(doc: Document, text: str, *, bold_lead: str | None = None) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.widow_control = True
    if bold_lead and text.startswith(bold_lead):
        first = paragraph.add_run(bold_lead)
        set_font(first, 10.5)
        first.bold = True
        rest = paragraph.add_run(text[len(bold_lead):])
        set_font(rest, 10.5)
    else:
        run = paragraph.add_run(text)
        set_font(run, 10.5)


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        paragraph = doc.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.left_indent = Inches(0.24)
        paragraph.paragraph_format.first_line_indent = Inches(-0.12)
        paragraph.paragraph_format.space_after = Pt(3)
        paragraph.paragraph_format.widow_control = True
        run = paragraph.add_run(item)
        set_font(run, 10.5)


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, value: int = 100) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side in ("top", "start", "bottom", "end"):
        node = tc_mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_borders(cell) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "4")
        node.set(qn("w:color"), BORDER)


def add_table(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
    widths: list[float] | None = None,
    numeric_columns: set[int] | None = None,
) -> None:
    numeric_columns = numeric_columns or set()
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    if widths is None:
        usable = 6.94 / len(headers)
        widths = [usable] * len(headers)

    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.width = Inches(widths[index])
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        shade_cell(cell, NAVY)
        set_cell_margins(cell, 110)
        set_cell_borders(cell)
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(header)
        set_font(run, 9)
        run.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)

    for row_index, values in enumerate(rows, start=1):
        cells = table.add_row().cells
        for index, value in enumerate(values):
            cell = cells[index]
            cell.width = Inches(widths[index])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            shade_cell(cell, PALE_BLUE if row_index % 2 else "FFFFFF")
            set_cell_margins(cell, 105)
            set_cell_borders(cell)
            paragraph = cell.paragraphs[0]
            paragraph.alignment = (
                WD_ALIGN_PARAGRAPH.CENTER if index in numeric_columns else WD_ALIGN_PARAGRAPH.LEFT
            )
            paragraph.paragraph_format.space_after = Pt(0)
            run = paragraph.add_run(str(value))
            set_font(run, 8.8)
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)


def add_figure(doc: Document, relative_path: str, caption: str, alt_text: str, width: float = 6.75) -> None:
    path = ROOT / relative_path
    if not path.exists():
        raise FileNotFoundError(path)
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run()
    inline = run.add_picture(str(path), width=Inches(width))
    c_nv_pr = inline._inline.graphic.graphicData.pic.nvPicPr.cNvPr
    c_nv_pr.set("descr", alt_text)
    caption_paragraph = doc.add_paragraph(caption, style="Caption")
    caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER


def add_equation(doc: Document, text: str) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(6)
    run = paragraph.add_run(text)
    set_font(run, 10.5, "Courier New")
    run.italic = True


def add_major_heading(doc: Document, text: str, *, page_break: bool = True) -> None:
    if page_break:
        doc.add_page_break()
    doc.add_heading(text, level=1)


def build() -> Document:
    doc = Document()
    configure_document(doc)

    # Cover
    cover_spacer = doc.add_paragraph()
    cover_spacer.paragraph_format.space_after = Pt(84)
    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("The Halftime Effect Final Project Documentation")
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(22)
    run = subtitle.add_run("Forecasting Great Britain electricity demand around England football matches")
    set_font(run, 14)
    run.font.color.rgb = RGBColor.from_string(NAVY)
    run.bold = True
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.paragraph_format.space_after = Pt(6)
    run = meta.add_run("Academic time-series forecasting project")
    set_font(run, 11)
    run.font.color.rgb = GRAY
    meta2 = doc.add_paragraph()
    meta2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = meta2.add_run("Final documentation  |  November 2026")
    set_font(run, 10.5)
    run.font.color.rgb = GRAY

    # Contents
    doc.add_page_break()
    doc.add_heading("Contents", level=1)
    contents = [
        "Executive summary",
        "1  Project background and research questions",
        "2  Data sources and target definition",
        "3  Data preparation and information safeguards",
        "4  Exploratory analysis of ordinary demand",
        "5  Autocorrelation and the seasonal benchmark",
        "6  Stationarity and spectral analysis",
        "7  Forecasting protocol and evaluation metrics",
        "8  Event-blind forecasting models",
        "9  Model diagnostics and uncertainty",
        "10  Locked January to March 2025 test",
        "11  Match-aware forecasting experiment",
        "12  Conclusions limitations and future work",
        "Appendix A  Model equations and inputs",
        "Appendix B  Reproducibility and project files",
    ]
    for item in contents:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(4)
        run = paragraph.add_run(item)
        set_font(run, 10.5)

    # Executive summary
    add_major_heading(doc, "Executive summary")
    add_text(
        doc,
        "This project investigates whether published England football fixture timing improves day-ahead forecasts of half-hourly Great Britain electricity demand. The analysis first models ordinary demand using calendar structure, leakage-safe demand history, archived weather forecasts, and embedded wind and solar forecasts. Football features are introduced only after establishing an event-blind baseline.",
    )
    add_text(
        doc,
        "Demand exhibits strong annual, daily and weekly patterns. The autocorrelation function shows high dependence at short, daily and weekly lags, while differencing and spectral analysis confirm that several seasonal structures remain in the raw series. These findings motivate a weekly seasonal-naive benchmark, calendar regression, multi-lag Ridge regression and residual time-series corrections.",
    )
    add_text(
        doc,
        "In four-fold development validation, weekly naive records 2,154 MW mean MAE, calendar plus weekly lag records 1,616 MW, and direct residual ARX records 1,348 MW. On the locked January to March 2025 test, direct residual ARX records 1,622 MW, compared with 3,101 MW for weekly naive and 781 MW for the external NESO forecast. A later development extension shows that issued weather and embedded-generation forecasts add substantial signal; direct residual ARX reaches 750 MW mean MAE in seven-fold development validation.",
    )
    add_text(
        doc,
        "The EURO 2024 match-aware experiment improves aggregate event-window MAE from 1,130 to 1,052 MW, but only three of seven fixtures improve. Halftime-proxy MAE worsens from 808 to 984 MW. The project therefore supports a stronger normal-demand forecasting model, but it does not verify a stable halftime-specific effect or a causal effect of football on demand.",
    )

    # 1
    add_major_heading(doc, "1  Project background and research questions")
    doc.add_heading("1.1 Motivation", level=2)
    add_text(
        doc,
        "Electricity demand can change rapidly when many consumers alter behaviour at similar times. England football matches are a plausible source of synchronized activity, particularly during scheduled breaks. However, national demand also changes systematically with clock time, weekday, season, holidays, weather and generation connected below the transmission system. A visible match-day change is therefore not sufficient evidence of a football effect.",
    )
    doc.add_heading("1.2 Research questions", level=2)
    add_bullets(
        doc,
        [
            "How accurately can normal half-hourly demand be forecast one day ahead using information available at the issue cutoff?",
            "Do published England fixture windows reduce forecast error after ordinary demand patterns have been modelled?",
            "Does any improvement occur specifically during the scheduled halftime proxy?",
        ],
    )
    doc.add_heading("1.3 Prediction and causality", level=2)
    add_text(
        doc,
        "The project makes a predictive claim, not a causal claim. A match-window coefficient may capture recurring forecast errors associated with tournament timing, weather, television audiences or omitted conditions. The analysis asks whether the schedule improves forecasts; it does not establish that football alone caused a particular MW change.",
    )

    # 2
    add_major_heading(doc, "2  Data sources and target definition")
    doc.add_heading("2.1 Primary target", level=2)
    add_text(
        doc,
        "The outcome is NESO Demand Outturn, renamed demand_mw. Each observation represents the demand level for one half-hour settlement interval. MW is a measure of power, not half-hour energy in MWh and not an instantaneous appliance pickup. The target represents national network demand rather than household consumption alone.",
    )
    add_table(
        doc,
        ["Source", "Information used", "Role"],
        [
            ["NESO demand forecast performance", "Demand outturn and NESO day-ahead forecast", "Target and external operational benchmark"],
            ["Calendar and bank holidays", "Date clock weekday and holiday indicators", "Deterministic demand structure"],
            ["Open-Meteo previous runs", "Archived issued temperature forecasts", "Day-ahead weather information"],
            ["NESO embedded forecasts", "Wind and solar forecasts capacities and issue times", "Visible net-demand information"],
            ["England fixture inventory", "Scheduled kickoff opponent stage and tournament", "Match-aware forecast features"],
        ],
        widths=[1.65, 2.55, 2.74],
    )
    doc.add_heading("2.2 Core and extended datasets", level=2)
    add_table(
        doc,
        ["Dataset scope", "Period", "Purpose"],
        [
            ["Core half-hour dataset", "January 2023 to July 2024", "EDA fixture coverage and EURO 2024 evaluation"],
            ["V2 event-blind dataset", "Historical training through March 2025", "Four-fold development and locked January to March 2025 test"],
            ["Exogenous forecast extension", "Historical development through December 2025", "Seven-fold validation of issued weather generation and residual models"],
        ],
        widths=[1.7, 2.0, 3.24],
    )
    add_text(
        doc,
        "The project treats the NESO operational demand forecast as an external comparison. It is never supplied as an input to the research models.",
    )

    # 3
    add_major_heading(doc, "3  Data preparation and information safeguards")
    doc.add_heading("3.1 Time representation", level=2)
    add_text(
        doc,
        "UTC is the primary ordering and joining key because each instant is unique. London time supplies human calendar labels such as weekday and clock position. Spring clock-change days contain 46 London settlement intervals and autumn days can contain 50, while the UTC sequence remains regular at 30-minute spacing.",
    )
    doc.add_heading("3.2 Validation checks", level=2)
    add_bullets(
        doc,
        [
            "Construct a complete 30-minute settlement grid and verify chronological continuity.",
            "Check duplicates missing demand values source record types units and positive numeric ranges.",
            "Confirm that source timestamps and settlement periods describe the same interval.",
            "Verify that forecast issue times precede the fixed day-ahead cutoff.",
            "Keep fixture labels and model splits explicit rather than inferring them from row order.",
        ],
    )
    doc.add_heading("3.3 Leakage prevention", level=2)
    add_text(
        doc,
        "The forecasting issue time is fixed at 10:00 London time on the preceding calendar day. Models cannot use target-day realized demand, realized weather or realized generation. Random train-test splitting is prohibited. Safe lags are created on the complete chronological series before evaluation rows are selected.",
    )
    add_text(
        doc,
        "For example, lag 1 is useful for understanding dependence, but tomorrow evening's preceding half-hour has not occurred when today's forecast is issued. A lag can be strongly correlated and still be operationally unavailable.",
    )

    # 4
    add_major_heading(doc, "4  Exploratory analysis of ordinary demand")
    doc.add_heading("4.1 Annual and intraday variation", level=2)
    add_figure(
        doc,
        "analyses/figures/demand_eda/01_training_halfhourly.png",
        "Figure 1  Half-hourly demand across the training period",
        "Half-hourly Great Britain electricity demand showing repeated daily movement and seasonal level changes",
    )
    add_text(
        doc,
        "Demand is generally higher in colder months and lower during summer. The later rise means that the winter-to-summer decline should not be described as a permanent downward trend. The dense band is created by repeated within-day rises and falls compressed across a long time axis.",
    )
    doc.add_heading("4.2 Weekday and seasonal profiles", level=2)
    add_figure(
        doc,
        "analyses/figures/demand_eda/04_weekday_mean_profiles.png",
        "Figure 2  Average local-time demand profiles by weekday",
        "Seven average weekday demand profiles showing working-day and weekend differences",
    )
    add_text(
        doc,
        "Working days show a pronounced morning rise and later peak. Weekend mornings rise less sharply, particularly on Sunday. In the pooled sample, the weekday profiles reach their maximum around the interval beginning at 18:00.",
    )
    add_figure(
        doc,
        "analyses/figures/demand_eda/08_monday_winter_summer.png",
        "Figure 3  Winter and summer Monday median profiles with interquartile bands",
        "Winter and summer Monday demand profiles showing seasonal differences in level shape and spread",
    )
    add_text(
        doc,
        "Winter Mondays remain above summer Mondays throughout the day and peak earlier. At 17:00, the median is approximately 38,948 MW in winter and 25,143 MW in summer. The shaded interquartile bands describe the middle 50 percent of observed values; they are not confidence or forecast intervals.",
    )
    doc.add_heading("4.3 EDA implications", level=2)
    add_bullets(
        doc,
        [
            "Normal demand requires time-of-day weekday and annual-seasonal features.",
            "Season changes the shape of the day as well as its overall level.",
            "A single same-time average is not an adequate counterfactual for a match interval.",
            "Descriptive plots suggest mechanisms but do not identify causes.",
        ],
    )

    # 5
    add_major_heading(doc, "5  Autocorrelation and the seasonal benchmark")
    add_figure(
        doc,
        "docs/presentation/assets/white_plots/08_acf_white.png",
        "Figure 4  Demand autocorrelation through one week",
        "Autocorrelation function of half-hourly demand through lag 336",
    )
    add_table(
        doc,
        ["Lag", "Elapsed time", "Correlation", "Operational interpretation"],
        [
            ["1", "30 minutes", "0.989", "Very strong persistence but unavailable for most day-ahead targets"],
            ["48", "24 hours", "0.914", "Strong daily repetition but partly unavailable at issue time"],
            ["336", "7 days", "0.893", "Strong weekly repetition and safely available"],
        ],
        widths=[0.6, 1.1, 1.0, 4.24],
        numeric_columns={0, 2},
    )
    add_text(
        doc,
        "The ACF oscillates with peaks around multiples of 48 half-hours and rises again toward the seven-day lag. Many raw-series lags are statistically significant because the sample is large and deterministic seasonality remains. This does not justify inserting every significant lag into an autoregression.",
    )
    doc.add_heading("5.1 Weekly seasonal-naive forecast", level=2)
    add_equation(doc, "forecast(t) = demand(t - 336)")
    add_text(
        doc,
        "The weekly rule has no estimated coefficients. It supplies a meaningful minimum standard because it usually aligns both weekday and clock phase and uses information already known at the day-ahead cutoff.",
    )

    # 6
    add_major_heading(doc, "6  Stationarity and spectral analysis")
    doc.add_heading("6.1 Transformations", level=2)
    add_figure(
        doc,
        "docs/presentation/assets/white_plots/09_transformations_white.png",
        "Figure 5  Original demand and first daily and weekly differences",
        "Original electricity demand followed by first daily seasonal and weekly seasonal differenced series",
    )
    add_text(
        doc,
        "First differencing focuses on adjacent changes. Daily differencing compares an observation with 48 half-hours earlier, and weekly differencing compares it with 336 half-hours earlier. The transformed means appear more stable, but seasonal dependence and changing variability remain.",
    )
    doc.add_heading("6.2 Unit-root tests", level=2)
    add_table(
        doc,
        ["Series", "ADF conclusion", "Phillips-Perron conclusion"],
        [
            ["Raw demand", "Fail to reject; p = 0.343", "Reject; p < 0.001"],
            ["First difference", "Reject unit-root null", "Reject unit-root null"],
            ["Daily difference", "Reject unit-root null", "Reject unit-root null"],
            ["Weekly difference", "Reject unit-root null", "Reject unit-root null"],
        ],
        widths=[2.1, 2.42, 2.42],
    )
    add_text(
        doc,
        "The disagreement for raw demand prevents a categorical claim based on one test. Rejecting a unit root after differencing does not prove white noise, constant variance or the absence of seasonality.",
    )
    doc.add_heading("6.3 Frequency-domain evidence", level=2)
    add_figure(
        doc,
        "analyses/figures/stationarity_spectral/07_periodogram_comparison.png",
        "Figure 6  Periodogram comparison for raw and differenced demand",
        "Periodograms comparing dominant frequencies before and after differencing",
        width=6.45,
    )
    add_text(
        doc,
        "The periodogram has power near one-seventh cycle per day, one cycle per day, and daily harmonics at two, three and four cycles per day. First differencing suppresses low frequencies. Daily and weekly differencing create notches at their corresponding seasonal frequencies. No transformed spectrum is flat, so none is white noise before modelling.",
    )

    # 7
    add_major_heading(doc, "7  Forecasting protocol and evaluation metrics")
    doc.add_heading("7.1 Chronological evaluation", level=2)
    add_text(
        doc,
        "Models are trained on earlier observations and evaluated on later observations. Rolling-origin folds are used for model selection, and choices are locked before the January to March 2025 V2 test is opened. The EURO 2024 match outcomes form a separate event holdout whose correction was fixed using earlier tournament editions.",
    )
    doc.add_heading("7.2 Metrics", level=2)
    add_equation(doc, "error = actual demand - forecast demand")
    add_table(
        doc,
        ["Metric", "Meaning", "Interpretation"],
        [
            ["Mean error", "Average signed error", "Positive means underforecasting; negative means overforecasting"],
            ["MAE", "Average absolute error", "Typical error magnitude; lower is better"],
            ["RMSE", "Square-root mean squared error", "Penalizes larger misses more strongly"],
        ],
        widths=[1.1, 2.2, 3.64],
    )
    add_text(
        doc,
        "Metrics are compared only when models forecast the same timestamps. Results from different periods or different experiment branches must not be treated as directly interchangeable.",
    )

    # 8
    add_major_heading(doc, "8  Event-blind forecasting models")
    doc.add_heading("8.1 V2 model progression", level=2)
    add_figure(
        doc,
        "docs/presentation/assets/white_plots/12_v2_selection_white.png",
        "Figure 7  Four-fold chronological validation of the V2 model progression",
        "Bar chart comparing mean validation MAE for weekly naive calendar Ridge residual AR direct ARX and NESO forecasts",
    )
    add_table(
        doc,
        ["Forecast", "Mean MAE", "Worst-fold MAE", "Purpose"],
        [
            ["Weekly seasonal naive", "2,154 MW", "2,966 MW", "One-week repetition benchmark"],
            ["Calendar plus weekly lag", "1,616 MW", "2,070 MW", "Deterministic seasonality plus current weekly level"],
            ["Multi-lag Ridge", "1,467 MW", "1,664 MW", "Regularized safe lags and calendar structure"],
            ["Ridge plus recursive residual AR", "1,381 MW", "1,529 MW", "Step-by-step residual correction"],
            ["Ridge plus direct residual ARX", "1,348 MW", "1,518 MW", "Direct correction at each target horizon"],
            ["NESO day-ahead", "623 MW", "690 MW", "External operational benchmark"],
        ],
        widths=[2.05, 1.05, 1.15, 2.69],
        numeric_columns={1, 2},
    )
    doc.add_heading("8.2 Ridge regression", level=2)
    add_text(
        doc,
        "Ridge regression estimates a linear forecast while penalizing the squared size of coefficients. The penalty stabilizes estimation when many calendar and lag variables are correlated. Inputs include half-hour-of-week effects, annual sine and cosine terms, trend, holiday indicators, safe daily and weekly lags, and lag summaries.",
    )
    doc.add_heading("8.3 Exogenous forecast ablation", level=2)
    add_figure(
        doc,
        "docs/presentation/assets/white_plots/13_v3_ablation_white.png",
        "Figure 8  Seven-fold Ridge feature-family comparison",
        "Bar chart comparing mean and worst-fold MAE for demand lags calendar weather embedded generation and combined inputs",
    )
    add_table(
        doc,
        ["Ridge feature family", "Mean MAE", "Worst-fold MAE"],
        [
            ["Reproduced demand-lag Ridge", "1,418 MW", "1,664 MW"],
            ["Rich calendar", "1,400 MW", "1,644 MW"],
            ["Issued weather forecasts", "1,265 MW", "1,336 MW"],
            ["Embedded wind and solar forecasts", "1,062 MW", "1,262 MW"],
            ["All exogenous inputs", "825 MW", "925 MW"],
            ["NESO day-ahead", "633 MW", "690 MW"],
        ],
        widths=[3.3, 1.75, 1.89],
        numeric_columns={1, 2},
    )
    add_text(
        doc,
        "The feature-family models are comparisons against the same reproduced base rather than a strictly cumulative sequence. The all-input model combines the information groups. Issued weather and embedded generation improve both average and worst-fold performance. Realized future weather or generation is never used.",
    )
    doc.add_heading("8.4 Residual error-correction models", level=2)
    add_text(
        doc,
        "A residual is actual demand minus the base forecast. Residual models estimate a correction and add it to the base forecast. Recursive AR feeds predicted residuals forward, ARMA models past residuals and innovations, and direct ARX predicts each horizon from cutoff-known residual history and exogenous inputs.",
    )
    add_equation(doc, "final forecast = base Ridge forecast + predicted residual")
    add_table(
        doc,
        ["Error-correction model", "Mean validation MAE", "Forecasting behaviour"],
        [
            ["Plain exogenous Ridge", "825 MW", "No dynamic residual correction"],
            ["Recursive AR 1 2 48 96", "777 MW", "Predictions feed later horizons"],
            ["ARMA 1 1", "802 MW", "Residual and innovation recursion"],
            ["ARMA 2 1 or 2 2", "818 MW", "Additional AR or MA terms do not improve MAE"],
            ["Direct residual ARX Ridge", "750 MW", "Direct horizon-specific correction; selected"],
        ],
        widths=[2.35, 1.45, 3.14],
        numeric_columns={1},
    )
    add_text(
        doc,
        "The daily seasonal SARIMAX candidate reached its iteration limit without reliable convergence and was rejected. Model complexity was retained only when it was interpretable, feasible and supported by chronological validation.",
    )

    # 9
    add_major_heading(doc, "9  Model diagnostics and uncertainty")
    doc.add_heading("9.1 Residual dependence", level=2)
    add_text(
        doc,
        "Forecast improvements did not make residuals independent. Residual ACF and Ljung-Box tests showed remaining within-day structure. This indicates that common day-level shocks and omitted operational inputs remain, rather than simply requiring an arbitrarily high autoregressive order.",
    )
    doc.add_heading("9.2 Conditional variance", level=2)
    add_text(
        doc,
        "ARCH-LM tests rejected constant conditional variance. A GARCH 1 1 model was fitted to describe changing residual scale. GARCH changes forecast intervals rather than the point forecast.",
    )
    add_table(
        doc,
        ["Diagnostic", "Development", "Locked 2025 test", "Interpretation"],
        [
            ["Variance persistence alpha plus beta", "0.980", "0.973", "Volatility regimes decay slowly"],
            ["Central 80 percent coverage", "80.5 percent", "75.7 percent", "Test interval under-covers"],
            ["Central 95 percent coverage", "93.6 percent", "90.1 percent", "Test interval under-covers"],
        ],
        widths=[2.05, 1.25, 1.35, 2.29],
        numeric_columns={1, 2},
    )
    add_text(
        doc,
        "Standardized residuals still failed ARCH and independence diagnostics. GARCH captured part of the changing scale but did not solve the remaining mean dynamics or deliver fully calibrated test intervals.",
    )

    # 10
    add_major_heading(doc, "10  Locked January to March 2025 test")
    add_text(
        doc,
        "The V2 model specification was locked before opening the January to March 2025 outcomes. The test contains 4,318 half-hour observations. This is the final locked test for the V2 branch; later exogenous-model comparisons are development-validation results and should not be presented as if they shared this untouched test.",
    )
    add_table(
        doc,
        ["Forecast", "Validation MAE", "Locked-test MAE", "Locked-test RMSE"],
        [
            ["Weekly seasonal naive", "2,154 MW", "3,101 MW", "3,955 MW"],
            ["Calendar plus weekly lag", "1,616 MW", "2,401 MW", "3,007 MW"],
            ["Direct residual ARX", "1,348 MW", "1,622 MW", "2,141 MW"],
            ["NESO day-ahead", "623 MW", "781 MW", "1,051 MW"],
        ],
        widths=[2.35, 1.4, 1.55, 1.64],
        numeric_columns={1, 2, 3},
    )
    add_text(
        doc,
        "Direct residual ARX reduces locked-test MAE by 47.7 percent relative to weekly naive and 32.4 percent relative to the calendar model. NESO remains substantially more accurate, indicating that the operational forecast contains day-specific information absent from the project model.",
    )

    # 11
    add_major_heading(doc, "11  Match-aware forecasting experiment")
    doc.add_heading("11.1 Scheduled-window features", level=2)
    add_text(
        doc,
        "The match-aware model adds fractional overlap features for pregame, scheduled play, a halftime proxy and post-match periods. A fraction of 0.5 means that 15 minutes of a half-hour interval lies inside the specified window. The halftime proxy covers scheduled minute 45 to 75 and is not a verified whistle-to-whistle break.",
    )
    add_equation(doc, "match-aware forecast = event-blind forecast + scheduled-window corrections")
    doc.add_heading("11.2 Selection without holdout leakage", level=2)
    add_text(
        doc,
        "The general-fixture experiment found no reliable improvement across mixed friendlies qualifiers and tournament matches. Tournament-specific selection therefore used 12 earlier fixtures from EURO 2020 and the 2022 World Cup. Complete tournament editions were held out during validation, and the selected four-window correction was locked before the seven EURO 2024 England fixtures were evaluated.",
    )
    add_text(
        doc,
        "The locked EURO 2024 experiment uses the event-blind calendar-and-weekly-lag baseline fixed at that stage. Later exogenous forecasting improvements were not retrofitted into the already opened tournament result.",
    )
    doc.add_heading("11.3 EURO 2024 results", level=2)
    add_figure(
        doc,
        "docs/presentation/assets/white_plots/16_euro_holdout_white.png",
        "Figure 9  EURO 2024 match-aware forecast evaluation",
        "Three-panel evaluation of aggregate event-window fixture-specific and window-specific match-aware forecast performance",
    )
    add_table(
        doc,
        ["Forecast", "Event-window MAE", "Event-window RMSE", "Mean error"],
        [
            ["Weekly seasonal naive", "1,143 MW", "1,583 MW", "-470 MW"],
            ["NESO day-ahead", "614 MW", "799 MW", "-349 MW"],
            ["Locked event-blind", "1,130 MW", "1,426 MW", "+909 MW"],
            ["Locked match-aware", "1,052 MW", "1,254 MW", "-550 MW"],
        ],
        widths=[2.15, 1.55, 1.55, 1.69],
        numeric_columns={1, 2, 3},
    )
    add_text(
        doc,
        "The aggregate match-aware forecast improves MAE by 77 MW or 6.8 percent relative to the event-blind forecast. However, only three of seven fixtures improve. A fixture-cluster bootstrap interval for the average MAE change crosses zero widely, so the average improvement is not stable with this event sample.",
    )
    add_table(
        doc,
        ["Window", "Event-blind MAE", "Match-aware MAE", "Result"],
        [
            ["Pregame", "1,424 MW", "1,265 MW", "158 MW better after rounding"],
            ["Scheduled match", "799 MW", "976 MW", "177 MW worse"],
            ["Halftime proxy", "808 MW", "984 MW", "176 MW worse"],
            ["Post-match", "1,032 MW", "866 MW", "166 MW better"],
        ],
        widths=[1.55, 1.65, 1.7, 2.04],
        numeric_columns={1, 2},
    )
    add_text(
        doc,
        "The pooled gain is driven by pregame and post-match observations. Scheduled-play and halftime-proxy performance becomes worse. The verified evidence therefore does not support a reliable halftime-aware forecast.",
    )

    # 12
    add_major_heading(doc, "12  Conclusions limitations and future work")
    doc.add_heading("12.1 Conclusions", level=2)
    add_bullets(
        doc,
        [
            "Great Britain electricity demand contains strong annual daily and weekly structure that must be modelled before event features are tested.",
            "Leakage-safe lags calendar effects issued weather and embedded-generation forecasts materially improve day-ahead accuracy.",
            "Direct residual ARX provides the best retained development-validation result among the agreed residual models.",
            "The V2 direct residual ARX model substantially beats weekly naive on the locked January to March 2025 test, while NESO remains stronger.",
            "Scheduled match timing modestly improves pooled EURO 2024 event-window MAE, but the result is inconsistent and halftime accuracy worsens.",
            "The study does not identify a causal football effect or a robust halftime-specific forecasting benefit.",
        ],
    )
    doc.add_heading("12.2 Limitations", level=2)
    add_bullets(
        doc,
        [
            "Seven EURO 2024 fixtures provide only seven event clusters, regardless of the number of half-hour rows.",
            "Scheduled windows approximate actual whistle times and the halftime proxy includes surrounding minutes.",
            "Half-hour data cannot isolate a short pickup lasting only a few minutes.",
            "Forecast-input errors and omitted system conditions remain in the residuals.",
            "Model relationships can change with demand regimes generation capacity and consumer behaviour.",
            "Observational schedule coefficients cannot separate football from all correlated conditions.",
        ],
    )
    doc.add_heading("12.3 Future work", level=2)
    add_bullets(
        doc,
        [
            "Pre-register event windows models metrics and uncertainty procedures before opening a new tournament.",
            "Add more tournament editions and retain one future edition as a completely untouched holdout.",
            "Use verified kickoff halftime restart and full-time timestamps.",
            "Use higher-frequency demand data when available to study short-lived pickup effects.",
            "Add forecast-available audience importance school-holiday and operational variables where defensible.",
            "Report fixture-cluster uncertainty and heterogeneous effects rather than relying on one pooled average.",
        ],
    )

    # Appendix A
    add_major_heading(doc, "Appendix A  Model equations and inputs")
    doc.add_heading("A.1 Weekly seasonal naive", level=2)
    add_equation(doc, "forecast(t) = demand(t - 336)")
    add_text(doc, "Input: demand exactly 336 half-hours earlier. Output: one half-hourly MW forecast.")

    doc.add_heading("A.2 Ridge regression", level=2)
    add_equation(doc, "forecast(t) = x(t) times estimated coefficients")
    add_text(
        doc,
        "The coefficient estimates minimize squared forecast error plus an L2 penalty. Inputs include calendar position, annual seasonal terms, holiday flags, leakage-safe daily and weekly lags, lag summaries, and, in the exogenous version, issued weather and embedded generation forecasts.",
    )

    doc.add_heading("A.3 Recursive residual AR", level=2)
    add_equation(doc, "residual(t) = intercept + weighted past residuals + innovation(t)")
    add_text(
        doc,
        "The main retained candidate uses residual lags 1, 2, 48 and 96. Unknown future residuals are replaced by earlier residual predictions, so errors can propagate across the forecast horizon.",
    )

    doc.add_heading("A.4 Direct residual ARX", level=2)
    add_equation(doc, "final forecast = base forecast + direct predicted residual")
    add_text(
        doc,
        "The correction uses only cutoff-known residual lags and summaries, forecast horizon, clock and weekday terms, the base forecast, holidays, weather, embedded wind and embedded solar. It predicts each target horizon directly rather than relying on future realized residuals.",
    )

    doc.add_heading("A.5 ARMA residual model", level=2)
    add_equation(doc, "residual(t) = AR terms + MA innovation terms + current innovation")
    add_text(
        doc,
        "ARMA candidates use orders 1 1, 2 1 and 2 2. They model compact stochastic residual dynamics but do not beat direct residual ARX in development validation.",
    )

    doc.add_heading("A.6 GARCH variance model", level=2)
    add_equation(doc, "variance(t) = constant + alpha times prior squared error + beta times prior variance")
    add_text(
        doc,
        "GARCH describes conditional variance and forecast intervals. It does not change the point forecast.",
    )

    doc.add_heading("A.7 Scheduled-window correction", level=2)
    add_equation(doc, "match forecast = event-blind forecast + pregame + play + halftime + post-match corrections")
    add_text(
        doc,
        "Each event feature is a fractional half-hour overlap derived from scheduled information. Coefficients estimate recurring predictive adjustments and are not causal effects.",
    )

    # Appendix B
    add_major_heading(doc, "Appendix B  Reproducibility and project files")
    doc.add_heading("B.1 Main processed data", level=2)
    add_table(
        doc,
        ["Path", "Purpose"],
        [
            ["data/processed/demand_development.csv", "Core training and validation demand analysis"],
            ["data/processed/demand_halfhour.csv", "Complete core half-hour table through July 2024"],
            ["data/processed/fixtures_all.csv", "Verified England fixture inventory"],
            ["data/processed/syllabus_aligned/demand_source.csv", "Extended leakage-safe forecast modelling panel"],
            ["data/processed/match_aware/modeling", "Match-aware selection predictions and evaluation metrics"],
        ],
        widths=[3.35, 3.59],
    )
    doc.add_heading("B.2 Main analysis documents", level=2)
    add_table(
        doc,
        ["Path", "Content"],
        [
            ["analyses/01_demand_eda_analysis.md", "Exploratory demand analysis"],
            ["analyses/02_autocorrelation_and_baselines_analysis.md", "ACF and seasonal-naive benchmark"],
            ["docs/event_blind_v2", "V2 experiment plan model selection and locked test"],
            ["docs/match_aware", "Fixture expansion correction selection and EURO 2024 holdout"],
            ["docs/presentation/01_verified_model_results.md", "Verified numerical source for presentation results"],
            ["docs/presentation/05_model_equations.md", "Retained equations inputs and metric definitions"],
        ],
        widths=[3.45, 3.49],
    )
    doc.add_heading("B.3 Principal scripts", level=2)
    add_table(
        doc,
        ["Script", "Purpose"],
        [
            ["src/finalize_data.py", "Construct and verify the core analysis dataset"],
            ["src/build_forecast_dataset.py", "Build the leakage-safe exogenous forecast panel"],
            ["src/evaluate_v2_regression_candidates.py", "Compare initial event-blind regression candidates"],
            ["src/evaluate_v2_direct_residual_candidates.py", "Select direct residual corrections"],
            ["src/evaluate_event_blind_v2_final_test.py", "Evaluate the locked January to March 2025 test"],
            ["src/evaluate_v3_ridge_ablation.py", "Compare issued exogenous feature families"],
            ["src/evaluate_presentation_scope_dynamics.py", "Compare retained residual dynamics"],
            ["src/select_tournament_correction.py", "Select the scheduled tournament correction"],
            ["src/evaluate_euro_2024_holdout.py", "Evaluate the locked EURO 2024 match-aware forecast"],
        ],
        widths=[3.6, 3.34],
    )
    add_text(
        doc,
        "The repository preserves separate model-selection and evaluation artifacts so reported results can be traced to their experiment stage. Rebuilding data from fresh sources creates a new data version and should not silently replace the frozen analysis inputs.",
    )

    return doc


def main() -> None:
    doc = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
