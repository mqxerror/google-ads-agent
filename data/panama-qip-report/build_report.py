#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build a self-contained, print-optimized static HTML report for the
Panama QIP - Oman + Jordan Google Search campaign plan.

Reads the real keyword data from panama-qip-kwp-processed.json and emits
report.html with NO external JS, NO CDN, system fonts only, print CSS for A4.
"""
import json
import html
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_JSON = os.path.join(
    BASE, "..", "panama-qip-kwp-processed.json"
)
OUT_HTML = os.path.join(BASE, "report.html")

with open(DATA_JSON, encoding="utf-8") as fh:
    DATA = json.load(fh)

ROWS = DATA["rows"]
TOTALS = DATA["totals_deduplicated"]

MONEY_KEYWORDS = {
    r["keyword"] for r in ROWS if "money term" in r["priority"]
}
# 4 keywords that returned real CPC bid data -> highlight
CPC_KEYWORDS = set(DATA["cpc_summary"]["keywords_with_bid_data"])


def esc(s):
    return html.escape(str(s), quote=True)


def vol_cell(disp):
    """Render a volume display value. '<10 / no data' -> muted <10."""
    if disp == "<10 / no data" or disp.startswith("<10"):
        return '<span class="mut">&lt;10</span>'
    return esc(disp)


def comp_cell(comp):
    if comp == "—":
        return '<span class="mut">&mdash;</span>'
    cls = {
        "Low": "comp-low",
        "Medium": "comp-med",
        "High": "comp-high",
    }.get(comp, "")
    return f'<span class="comp {cls}">{esc(comp)}</span>'


def cpc_cell(cpc, is_cpc_kw):
    if cpc == "no data":
        return '<span class="mut">no data</span>'
    cls = "cpc-hi" if is_cpc_kw else ""
    return f'<span class="{cls}">{esc(cpc)}</span>'


def prio_cell(prio):
    if "money term" in prio:
        return '<span class="pill pill-money">P1 &middot; money</span>'
    if "reach" in prio:
        return '<span class="pill pill-reach">P1 &middot; reach</span>'
    if prio == "P2":
        return '<span class="pill pill-p2">P2</span>'
    if "long-tail" in prio:
        return '<span class="pill pill-p3">P3 &middot; long-tail</span>'
    return esc(prio)


def build_keyword_rows():
    """All 121 keywords, sorted volume-desc (vol_max), stable by keyword."""
    ordered = sorted(
        ROWS, key=lambda r: (-r["vol_max"], r["keyword"])
    )
    out = []
    for i, r in enumerate(ordered, start=1):
        is_ar = r["lang"] == "AR"
        is_money = r["keyword"] in MONEY_KEYWORDS
        is_cpc = r["keyword"] in CPC_KEYWORDS
        row_cls = []
        if is_ar:
            row_cls.append("ar-row")
        if is_money:
            row_cls.append("money-row")
        cls_attr = f' class="{" ".join(row_cls)}"' if row_cls else ""

        lang_badge = (
            '<span class="lang lang-ar">AR</span>'
            if is_ar
            else '<span class="lang lang-en">EN</span>'
        )

        money_badge = (
            ' <span class="badge-money">PANAMA</span>' if is_money else ""
        )

        if is_ar:
            translit = esc(r.get("translit", ""))
            gloss = esc(r.get("gloss", ""))
            kw_html = (
                f'<span class="kw-ar" dir="rtl" lang="ar">{esc(r["keyword"])}</span>'
                f'{money_badge}'
                f'<span class="kw-sub"><i>{translit}</i> &mdash; &ldquo;{gloss}&rdquo;</span>'
            )
        else:
            kw_html = f'<span class="kw-en">{esc(r["keyword"])}</span>{money_badge}'

        out.append(
            f"<tr{cls_attr}>"
            f'<td class="num">{i}</td>'
            f'<td class="kw">{kw_html}</td>'
            f'<td class="ctr">{lang_badge}</td>'
            f'<td class="ctr">{vol_cell(r["vol_oman_disp"])}</td>'
            f'<td class="ctr">{vol_cell(r["vol_jordan_disp"])}</td>'
            f'<td class="ctr">{comp_cell(r["competition"])}</td>'
            f'<td class="ctr">{cpc_cell(r["cpc"], is_cpc)}</td>'
            f'<td class="ctr">{prio_cell(r["priority"])}</td>'
            f"</tr>"
        )
    return "\n".join(out)


KEYWORD_ROWS = build_keyword_rows()

# ---------------------------------------------------------------------------
# Static HTML assembly
# ---------------------------------------------------------------------------

CSS = r"""
:root{
  --navy:#0B1F3A;
  --navy-2:#12305c;
  --navy-soft:#1b3a63;
  --gold:#C79A3A;
  --gold-soft:#E4C878;
  --ink:#1a1f26;
  --ink-soft:#3a4653;
  --mut:#8a97a6;
  --line:#d8dee6;
  --line-soft:#e9edf2;
  --paper:#ffffff;
  --band:#f4f6f9;
  --band-2:#eef2f7;
}
*{box-sizing:border-box;}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact;}
body{
  margin:0;
  font-family:-apple-system,"Helvetica Neue",Arial,sans-serif;
  color:var(--ink);
  font-size:11.5px;
  line-height:1.5;
  background:var(--paper);
}
.kw-ar,[dir="rtl"],[lang="ar"]{
  font-family:"Geeza Pro","Noto Naskh Arabic","Al Bayan",serif;
}
h1,h2,h3,h4{margin:0;line-height:1.25;font-weight:700;color:var(--navy);}
p{margin:0 0 8px 0;}
a{color:var(--navy-2);text-decoration:none;}
strong{font-weight:700;color:var(--ink);}
em{font-style:italic;}
.wrap{max-width:190mm;margin:0 auto;padding:0 2mm;}

/* ---------- Cover ---------- */
.cover{
  background:linear-gradient(150deg,var(--navy) 0%,var(--navy-2) 62%,var(--navy-soft) 100%);
  color:#fff;
  padding:26px 26px 22px 26px;
  border-radius:4px;
  position:relative;
  overflow:hidden;
  margin-bottom:16px;
}
.cover:after{
  content:"";position:absolute;right:-60px;top:-60px;width:220px;height:220px;
  border:2px solid rgba(199,154,58,.28);border-radius:50%;
}
.cover:before{
  content:"";position:absolute;right:-20px;bottom:-90px;width:180px;height:180px;
  border:2px solid rgba(199,154,58,.16);border-radius:50%;
}
.cover .eyebrow{
  color:var(--gold-soft);font-size:11px;font-weight:700;letter-spacing:.22em;
  text-transform:uppercase;margin-bottom:12px;
}
.cover h1{color:#fff;font-size:29px;letter-spacing:-.01em;margin-bottom:6px;}
.cover .sub{color:#e9eef6;font-size:14px;font-weight:500;margin-bottom:18px;}
.cover .rule{height:3px;width:64px;background:var(--gold);border-radius:2px;margin:14px 0 16px;}
.cover .meta{display:flex;flex-wrap:wrap;gap:8px 26px;position:relative;z-index:2;}
.cover .meta div{font-size:11px;color:#d7deea;}
.cover .meta b{display:block;color:#fff;font-size:12.5px;font-weight:700;letter-spacing:.01em;margin-top:1px;}
.cover .prep{
  margin-top:16px;padding-top:12px;border-top:1px solid rgba(255,255,255,.16);
  font-size:11px;color:#cdd6e4;position:relative;z-index:2;
}
.cover .prep b{color:var(--gold-soft);}

/* ---------- Provenance strip ---------- */
.prov{
  border:1px solid var(--line);border-left:4px solid var(--gold);
  background:var(--band);border-radius:3px;padding:9px 13px;margin-bottom:14px;
  font-size:10px;color:var(--ink-soft);
}
.prov b{color:var(--navy);}

/* ---------- Sections ---------- */
section{margin-bottom:16px;}
.sec-head{display:flex;align-items:baseline;gap:10px;
  border-bottom:2px solid var(--navy);padding-bottom:5px;margin-bottom:11px;}
.sec-num{
  background:var(--navy);color:var(--gold-soft);font-weight:700;font-size:11px;
  width:20px;height:20px;border-radius:4px;display:inline-flex;align-items:center;
  justify-content:center;flex:0 0 auto;
}
.sec-head h2{font-size:16px;letter-spacing:-.01em;}
h3{font-size:12.5px;margin:12px 0 6px;color:var(--navy-2);}
h4{font-size:11.5px;margin:9px 0 4px;color:var(--ink-soft);}

/* ---------- Stat blocks ---------- */
.stats{display:flex;gap:9px;flex-wrap:wrap;margin:10px 0 4px;}
.stat{
  flex:1 1 0;min-width:96px;border:1px solid var(--line);border-radius:5px;
  background:#fff;padding:11px 12px;border-top:3px solid var(--gold);
}
.stat .n{font-size:23px;font-weight:800;color:var(--navy);line-height:1;letter-spacing:-.02em;}
.stat .l{font-size:9.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.09em;
  margin-top:5px;font-weight:700;}
.stat .d{font-size:10px;color:var(--ink-soft);margin-top:4px;line-height:1.35;}

/* ---------- Callouts ---------- */
.callout{
  border:1px solid var(--line);border-left:4px solid var(--gold);
  background:linear-gradient(180deg,#fbf7ee,#f7f1e2);
  border-radius:4px;padding:11px 14px;margin:11px 0;
}
.callout .ct{font-weight:800;color:var(--navy);font-size:11.5px;
  text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;}
.callout.note{
  background:var(--band);border-left-color:var(--navy-2);
}
.callout.note .ct{color:var(--navy-2);}

.lever{
  border:1.5px solid var(--gold);border-radius:5px;overflow:hidden;margin:11px 0;
}
.lever .lh{background:var(--navy);color:#fff;padding:8px 14px;font-weight:700;font-size:12px;}
.lever .lh span{color:var(--gold-soft);}
.lever .lb{padding:11px 14px;background:#fff;}
.lever .lb ul{margin:6px 0 0;padding-left:18px;}
.lever .lb li{margin-bottom:3px;}
.big-num{color:var(--gold);font-weight:800;}

/* ---------- Tables ---------- */
table{border-collapse:collapse;width:100%;margin:8px 0 4px;font-size:10px;}
.tbl-rec th,.tbl-rec td{padding:6px 9px;text-align:left;vertical-align:top;
  border-bottom:1px solid var(--line-soft);}
.tbl-rec thead th{
  background:var(--navy);color:#fff;font-weight:700;font-size:9.5px;
  text-transform:uppercase;letter-spacing:.04em;border-bottom:none;
}
.tbl-rec tbody tr:nth-child(even){background:var(--band);}
.tbl-rec td b{color:var(--navy-2);}
.wide-first td:first-child,.wide-first th:first-child{width:26%;font-weight:600;}

/* budget tables narrower numeric */
.tbl-num td,.tbl-num th{text-align:center;}
.tbl-num td:first-child,.tbl-num th:first-child{text-align:left;}

/* ---------- Keyword mega table ---------- */
.kw-table-wrap{margin-top:8px;}
table.kw{font-size:9px;width:100%;border-collapse:collapse;}
table.kw thead th{
  background:var(--navy);color:#fff;font-weight:700;font-size:8.5px;
  text-transform:uppercase;letter-spacing:.03em;padding:5px 6px;text-align:center;
  border-bottom:2px solid var(--gold);
}
table.kw thead th.kwh{text-align:left;}
table.kw td{padding:4px 6px;border-bottom:1px solid var(--line-soft);vertical-align:top;}
table.kw td.num{color:var(--mut);text-align:center;width:22px;font-variant-numeric:tabular-nums;}
table.kw td.ctr{text-align:center;}
table.kw tbody tr:nth-child(even){background:#f7f9fb;}
table.kw tbody tr.money-row{background:#fbf6ea;}
table.kw tbody tr.money-row:nth-child(even){background:#f7f0dd;}
.kw-en{font-weight:600;color:var(--ink);}
.kw-ar{font-weight:600;color:var(--ink);font-size:11px;display:inline-block;}
.kw-sub{display:block;color:var(--mut);font-size:8px;line-height:1.3;margin-top:1px;}
.kw-sub i{font-style:italic;}
.mut{color:var(--mut);}
.lang{display:inline-block;font-size:7.5px;font-weight:800;padding:1px 5px;border-radius:3px;
  letter-spacing:.04em;}
.lang-en{background:#e6eef7;color:#1c3f6e;}
.lang-ar{background:#efe7d6;color:#7a5a15;}
.comp{display:inline-block;font-size:8px;font-weight:700;padding:1px 5px;border-radius:8px;}
.comp-low{background:#e5f1e8;color:#2f6b41;}
.comp-med{background:#fdf1dd;color:#8a5a12;}
.comp-high{background:#f9e4e2;color:#8f3a30;}
.cpc-hi{background:#fbeecb;color:#7a5410;font-weight:700;padding:1px 4px;border-radius:3px;}
.badge-money{
  display:inline-block;font-size:7px;font-weight:800;letter-spacing:.06em;
  background:var(--gold);color:#3a2c08;padding:1px 4px;border-radius:3px;margin-left:5px;
  vertical-align:middle;
}
.pill{display:inline-block;font-size:7.5px;font-weight:700;padding:1px 5px;border-radius:8px;white-space:nowrap;}
.pill-money{background:var(--navy);color:var(--gold-soft);}
.pill-reach{background:#dfe9f4;color:#1c3f6e;}
.pill-p2{background:#eceff3;color:#4a5867;}
.pill-p3{background:#f2f3f5;color:#8a97a6;}

.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:9px;color:var(--ink-soft);
  margin:8px 0;padding:8px 12px;background:var(--band);border-radius:4px;border:1px solid var(--line-soft);}
.legend b{color:var(--navy);}
.legend .sw{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:-1px;margin-right:3px;}

ul.tight{margin:4px 0 8px;padding-left:18px;}
ul.tight li{margin-bottom:3px;}
.neg-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px 18px;font-size:10px;margin:6px 0;}
.neg-grid div{padding:3px 0;border-bottom:1px dotted var(--line);}
.neg-grid b{color:var(--navy-2);}
.rtl-inline{font-family:"Geeza Pro","Noto Naskh Arabic","Al Bayan",serif;direction:rtl;unicode-bidi:isolate;}

/* ---------- Footer ---------- */
.foot{
  margin-top:18px;border-top:2px solid var(--navy);padding-top:10px;
  font-size:9px;color:var(--ink-soft);
}
.foot b{color:var(--navy);}
.foot .prov-line{margin-top:6px;color:var(--mut);}

/* ---------- Print ---------- */
@page{ size:A4; margin:16mm; }
@media print{
  body{font-size:11px;}
  .no-print{display:none;}
  thead{display:table-header-group;}
  tr,.card,.stat,.callout,.lever,.sec-head{page-break-inside:avoid;}
  section{page-break-inside:auto;}
  .page-break{page-break-before:always;}
  table.kw tbody tr{page-break-inside:avoid;}
  .cover{page-break-after:avoid;}
}
"""


def stat_block(n, label, desc):
    return (
        f'<div class="stat"><div class="n">{n}</div>'
        f'<div class="l">{label}</div>'
        f'<div class="d">{desc}</div></div>'
    )


HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Panama QIP &middot; Oman + Jordan &middot; Google Search Campaign Plan</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

  <!-- ============ COVER ============ -->
  <header class="cover">
    <div class="eyebrow">Mercan Group &middot; Campaign Plan &amp; Traffic Sizing</div>
    <h1>Panama Qualified Investor Program</h1>
    <div class="sub">Oman&nbsp;+&nbsp;Jordan &middot; Google Search &middot; English&nbsp;+&nbsp;Arabic</div>
    <div class="rule"></div>
    <div class="meta">
      <div>Program<b>Panama QIP / QIV &mdash; the &ldquo;Panama Golden Visa&rdquo;</b></div>
      <div>Markets<b>Oman &amp; Jordan</b></div>
      <div>Channel<b>Google Search (Search Partners off)</b></div>
      <div>Languages<b>English + Arabic</b></div>
      <div>Date<b>2026-07-06</b></div>
      <div>Status<b>Build-ready, data-backed operator brief</b></div>
    </div>
    <div class="prep">
      Prepared by <b>Mercan Group</b> &mdash; the only company worldwide with an official
      Government-of-Panama partnership for the Qualified Investor Program.
      Landing page: www.mercan.com/lp/panama-qualified-investor-program
    </div>
  </header>

  <div class="prov">
    <b>Data provenance.</b> All search-volume and CPC figures were pulled from
    <b>Google Keyword Planner via the Google Ads API (v23)</b>
    (KeywordPlanIdeaService.GenerateKeywordHistoricalMetrics) for geographies
    <b>Oman</b> and <b>Jordan</b>, languages <b>English</b> and <b>Arabic</b>,
    network <b>Google Search</b>, over the <b>last 12 months</b>. Keyword Planner reports
    volume as rounded ranges (10 / 20 / 30&hellip;), not exact counts &mdash; treat every figure
    as <b>directional sizing, not a guarantee</b> of clicks or conversions. Terms marked
    <span class="mut">&lt;10</span> fall below Keyword Planner&rsquo;s ~10 searches/month reporting
    floor: that is genuinely how much search there is. These are small, high-value niche markets.
  </div>

  <!-- ============ 1. EXECUTIVE SUMMARY ============ -->
  <section>
    <div class="sec-head"><span class="sec-num">1</span><h2>Executive summary</h2></div>
    <p>There is real, capturable demand in Oman and Jordan for a <strong>second residency /
    second passport / family &ldquo;Plan B&rdquo;</strong> &mdash; two under-served Gulf and Levant
    markets with high per-capita wealth, strong mobility motives, and (for Jordan especially) an
    active search for a stronger passport and a stable, dollar-based base. This campaign puts
    Mercan&rsquo;s Panama QIP in front of that audience on Google Search, in both English and Arabic.</p>

    <h3>The honest reality, stated up front</h3>
    <ul class="tight">
      <li><strong>Total addressable demand is roughly 950 searches/month</strong> across every
      keyword researched, both countries, both languages (deduplicated). That is a small, premium
      niche &mdash; not a high-volume market.</li>
      <li><strong>Panama-specific terms are near-zero volume.</strong> Almost every
      &ldquo;panama golden visa / <span class="rtl-inline">برنامج المستثمر المؤهل</span>&rdquo; style
      term returns <span class="mut">&lt;10</span> here &mdash; very few people in Oman/Jordan search
      for <em>Panama</em> by name yet. Expected, not an error.</li>
      <li><strong>The strategy splits reach from intent.</strong> Broad head terms
      (<em>golden visa</em>, <em>residency by investment</em>, <em>citizenship by investment</em>,
      and the Arabic <span class="rtl-inline">الإقامة الذهبية</span> / <span class="rtl-inline">الفيزا الذهبية</span>)
      carry the <strong>reach</strong>; Panama-specific terms carry the <strong>intent</strong>
      (whoever types them is already sold on Panama). Bid to capture both.</li>
      <li><strong>English leads.</strong> Investment-migration is a globalised, English-jargon
      category; even Arabic-speaking Gulf/Levant investors (and their bankers and advisors)
      overwhelmingly search the industry terms in English. Arabic is real and often cheaper, but
      broader and earlier-funnel.</li>
      <li><strong>The strongest CTA lever is a real deadline.</strong> Panama&rsquo;s real-estate
      threshold is scheduled to rise from <strong>USD&nbsp;300,000 to USD&nbsp;500,000 in
      October&nbsp;2026</strong> &mdash; a legitimate &ldquo;act before the price rises, save
      $200K&rdquo; hook that should headline sitelinks and callouts while live.</li>
    </ul>

    <h3>Market shape at a glance</h3>
    <div class="stats">
      {stat_block("680", "English / mo", "Where ready-to-invest intent + reach concentrate")}
      {stat_block("270", "Arabic / mo", "Real, broader/earlier demand; often cheaper CPCs")}
      {stat_block("460", "Oman / mo", "Near-even with Jordan")}
      {stat_block("490", "Jordan / mo", "Near-even; strong Plan-B motive")}
      {stat_block("~950", "Total / mo", "Full addressable market, both langs, both countries")}
    </div>
    <div class="callout note">
      <div class="ct">Bottom line</div>
      This is a <strong>precision, high-value-per-lead</strong> campaign, not a volume play.
      Success is measured in <strong>cost-per-qualified-lead</strong>, not clicks or impressions.
    </div>
  </section>

  <!-- ============ 2. RECOMMENDATIONS ============ -->
  <section class="page-break">
    <div class="sec-head"><span class="sec-num">2</span><h2>Recommendations</h2></div>

    <h3>2.1 &nbsp;Campaign structure</h3>
    <table class="tbl-rec wide-first">
      <thead><tr><th>Setting</th><th>Recommendation</th><th>Why</th></tr></thead>
      <tbody>
        <tr><td>Channel</td><td><b>Search only</b></td><td>Precision audience on a small budget</td></tr>
        <tr><td>Search Partners</td><td><b>OFF</b></td><td>Dilutes a narrow HNW audience; revisit once data is clean</td></tr>
        <tr><td>Display Network</td><td><b>OFF</b></td><td>No display for a precision search test</td></tr>
        <tr><td>Campaigns (target design)</td><td>An <b>English campaign</b> + a parallel <b>Arabic campaign</b> &mdash; but at the launch budget, consolidate to one <b>English-first</b> campaign (see &sect;3)</td><td>Clean per-language budget control + native ad copy + clean CPL read <em>once budget supports it</em></td></tr>
        <tr><td>Geo targeting</td><td><b>Oman + Jordan</b>, location option <b>&ldquo;Presence: people in your targeted locations&rdquo;</b> (NOT presence-or-interest)</td><td>We want people physically in Oman/Jordan, not everyone worldwide merely interested</td></tr>
        <tr><td>Language targeting</td><td>English on EN campaign, Arabic on AR campaign &mdash; but Google keys language off the user&rsquo;s browser/interface, not the query. The real split is enforced by the <b>keyword list</b></td><td>Do not rely on language targeting alone to separate the two</td></tr>
        <tr><td>Devices</td><td>Start all devices; monitor mobile vs desktop</td><td>HNW research often starts on mobile, converts on desktop/phone-call &mdash; don&rsquo;t cut mobile early</td></tr>
        <tr><td>Ad schedule</td><td>All-week to start; review hour/day after 2 weeks</td><td>Let data decide, not assumptions</td></tr>
      </tbody>
    </table>

    <h3>2.2 &nbsp;Ad groups &mdash; six, mirroring the six keyword clusters</h3>
    <p>Each campaign is organised into <strong>6 tightly-themed ad groups</strong>, one per intent
    cluster, so every ad speaks to exactly the searcher&rsquo;s mindset.</p>
    <table class="tbl-rec">
      <thead><tr><th>Ad group</th><th>Cluster</th><th>Priority</th><th>Note</th></tr></thead>
      <tbody>
        <tr><td><b>AG1 &middot; Golden / Investor Visa</b></td><td>A</td><td>High reach</td><td>Category entry point; broadest head terms (<em>golden visa</em>)</td></tr>
        <tr><td><b>AG2 &middot; Residency by Investment</b></td><td>B</td><td>High reach</td><td>The precise category label; research&rarr;ready bridge</td></tr>
        <tr><td><b>AG3 &middot; Citizenship / 2nd Passport</b></td><td>C</td><td>High emotion</td><td><b>Honest copy only</b> &mdash; Panama is residency now &rarr; citizenship eligibility after 5&nbsp;yrs, never instant</td></tr>
        <tr><td><b>AG4 &middot; Panama-specific</b></td><td>D</td><td><b>Highest intent</b></td><td>Lowest volume, readiest buyers &mdash; <b>bid up</b>, [exact], sharpest ads</td></tr>
        <tr><td><b>AG5 &middot; Tax / Plan-B / Base</b></td><td>E</td><td>Research</td><td>Softer CTA; feeds remarketing later</td></tr>
        <tr><td><b>AG6 &middot; Comparison / Best-Cheapest-Fastest</b></td><td>F</td><td>Commercial shopper</td><td>Lead with $300K + 30-day speed + 142-country access</td></tr>
      </tbody>
    </table>
    <div class="callout note">
      <div class="ct">AG3 honesty note</div>
      Panama is a <strong>residency &rarr; citizenship-after-5-years</strong> route, <strong>not</strong>
      instant citizenship. All AG3 ad copy must frame it as &ldquo;permanent residency now, a clear
      path to citizenship after 5 years.&rdquo;
    </div>

    <h3>2.3 &nbsp;Bidding</h3>
    <ul class="tight">
      <li><strong>Start on <code>Maximize Conversions</code></strong> on both campaigns &mdash;
      <strong>no target CPA yet.</strong> A brand-new campaign has zero conversion history to feed a
      target, so tCPA would starve delivery.</li>
      <li><strong>Primary conversion action:</strong> the LP&rsquo;s main lead event (consultation
      request / guide download / tap-to-call). Confirm the QIP landing page fires <strong>its own
      distinct lead conversion</strong> into Google Ads &mdash; ideally through the existing GTM
      container (<code>GTM-K6864NBH</code>) with <strong>Enhanced Conversions</strong> on &mdash; so
      this campaign optimises on <em>its own</em> leads, not blended Mercan activity.</li>
      <li><strong>Graduate to tCPA after ~15&ndash;30 conversions</strong>, once a real
      cost-per-lead is known.</li>
      <li><strong>AG4 (Panama-specific):</strong> bias bids <strong>up</strong> &mdash; readiest
      buyers at the lowest volume, so aggressive bids on tiny traffic are affordable.</li>
    </ul>

    <h3>2.4 &nbsp;Negative keywords (protect a narrow budget)</h3>
    <p>Apply a shared negative list at <strong>campaign level</strong> on both campaigns to strip
    adjacent-but-worthless traffic that never invests USD&nbsp;300K. Summarised (full EN + AR sets
    held in the strategy file):</p>
    <div class="neg-grid">
      <div><b>Jobs / work</b> &mdash; jobs, vacancy, hiring, salary, work visa, work permit &middot; <span class="rtl-inline">وظائف، عمل، تأشيرة عمل، راتب</span></div>
      <div><b>Tourism / travel</b> &mdash; tourist, vacation, hotel booking, flights, airbnb &middot; <span class="rtl-inline">سياحة، فندق، طيران</span></div>
      <div><b>Study</b> &mdash; student, study, scholarship, university, school &middot; <span class="rtl-inline">دراسة، منحة</span></div>
      <div><b>Retire / lifestyle</b> &mdash; retire, retirement, retiree, pensionado</div>
      <div><b>Cheap-relocation</b> &mdash; cost of living, rent, cheap living, budget, digital nomad &middot; <span class="rtl-inline">تكلفة المعيشة، إيجار، رخيص للسكن</span></div>
      <div><b>Free / humanitarian</b> &mdash; free, grant, asylum, refugee, embassy appointment &middot; <span class="rtl-inline">مجاني، لجوء، لاجئ</span></div>
      <div><b>Stray</b> &mdash; map, weather, spanish course, translation &middot; <span class="rtl-inline">ترجمة</span></div>
    </div>
    <div class="callout">
      <div class="ct">Ongoing hygiene</div>
      Run the <strong>Search Terms report twice weekly</strong> for the first month and harvest
      negatives aggressively &mdash; a small budget cannot absorb waste. Watch for other-country
      golden-visa searches: decide per term whether to exclude or redirect into AG6 (comparison).
    </div>

    <h3>2.5 &nbsp;The October-2026 urgency lever</h3>
    <div class="lever">
      <div class="lh">USD&nbsp;<span class="big-num">300K</span> &rarr; USD&nbsp;<span class="big-num">500K</span> threshold rise &mdash; October 2026 &middot; the single strongest CTA</div>
      <div class="lb">
        Deploy while live; retire if the deadline moves.
        <ul>
          <li><strong>Sitelink (EN):</strong> &ldquo;Before the Oct 2026 Threshold Rise&rdquo; &rarr; deep-link to the LP consultation</li>
          <li><strong>Sitelink (AR):</strong> <span class="rtl-inline">قبل ارتفاع الحد الأدنى</span> (&ldquo;before the minimum rises&rdquo;)</li>
          <li><strong>Callout:</strong> &ldquo;Invest at USD&nbsp;300K &mdash; before it rises&rdquo; / &ldquo;Save $200K vs the 2026 increase&rdquo;</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- ============ 3. BUDGET PLAN ============ -->
  <section class="page-break">
    <div class="sec-head"><span class="sec-num">3</span><h2>Budget plan &mdash; $30/day (a beachhead, not a scale budget)</h2></div>
    <div class="callout">
      <div class="ct">The recommendation</div>
      At $30/day, run <strong>English-first across BOTH countries as a single campaign</strong> to
      gather signal. <strong>Do not fragment into four cells.</strong> This is a deliberate departure
      from the strategy document&rsquo;s day-one 70/30 two-campaign split &mdash; that parallel-Arabic
      structure is right <em>once budget reaches roughly $75&ndash;150/day.</em> At $30/day it spreads
      spend too thin to learn.
    </div>

    <h3>3.1 &nbsp;What $30/day buys (one English-first campaign, both countries)</h3>
    <p>This is a <strong>premium-CPC category</strong> &mdash; golden-visa / citizenship-by-investment
    clicks are among the most expensive in paid search. Actual CPC paid usually sits below the
    top-of-page bid, so we model an effective-CPC band:</p>
    <table class="tbl-rec tbl-num">
      <thead><tr><th>Effective CPC</th><th>Scenario</th><th>Clicks/day at full $30</th><th>Clicks/month (~30d)</th></tr></thead>
      <tbody>
        <tr><td><b>$2.50</b></td><td>Optimistic &mdash; Jordan / Arabic-leaning, cheaper clicks</td><td><b>12.0</b></td><td>~360</td></tr>
        <tr><td><b>$4.00</b></td><td>Mid &mdash; blended English</td><td><b>7.5</b></td><td>~225</td></tr>
        <tr><td><b>$6.00</b></td><td>Conservative &mdash; premium English, Oman-weighted</td><td><b>5.0</b></td><td>~150</td></tr>
      </tbody>
    </table>
    <p>&rarr; Roughly <strong>150&ndash;360 clicks/month.</strong> Modest by design &mdash; enough to
    read direction and cost-per-lead, not to chase scale.</p>

    <h3>3.2 &nbsp;Why NOT split into four cells</h3>
    <p>Splitting $30/day across four cells &mdash; EN-Oman, EN-Jordan, AR-Oman, AR-Jordan &mdash;
    leaves <strong>$7.50/day each</strong>:</p>
    <table class="tbl-rec tbl-num">
      <thead><tr><th>Per-cell budget</th><th>@ $6 CPC</th><th>@ $4 CPC</th></tr></thead>
      <tbody>
        <tr><td><b>$7.50/day</b></td><td><b>1.2 clicks/day</b></td><td><b>1.9 clicks/day</b></td></tr>
      </tbody>
    </table>
    <div class="callout note">
      <div class="ct">Don&rsquo;t split four ways</div>
      That is <strong>below the ~2 clicks/day floor</strong> a Maximize-Conversions campaign needs to
      exit the learning phase. Splitting starves every cell &mdash; four campaigns that each learn
      nothing beats one campaign that learns. Consolidate now; layer Arabic and per-country geo
      splits only when budget scales.
    </div>

    <h3>3.3 &nbsp;Scaled scenarios (when to graduate)</h3>
    <table class="tbl-rec tbl-num">
      <thead><tr><th>Daily budget</th><th>Split</th><th>Eff. CPC</th><th>Clicks/day</th><th>Clicks/mo</th><th>Milestone</th></tr></thead>
      <tbody>
        <tr><td><b>$30</b></td><td>EN-first, one campaign, both countries</td><td>$4.00</td><td>~7.5</td><td>~225</td><td>Beachhead &mdash; prove CPL &amp; direction</td></tr>
        <tr><td><b>$75</b></td><td>EN $52 + AR $23</td><td>$4.00</td><td>~19</td><td>~560</td><td>Split Arabic into its own campaign</td></tr>
        <tr><td><b>$150</b></td><td>EN $105 + AR $45</td><td>$4.00</td><td>~38</td><td>~1,125</td><td>Volume to graduate to tCPA + consider per-country geo splits</td></tr>
      </tbody>
    </table>
    <div class="callout">
      <div class="ct">Read this as a beachhead &middot; English-first recommendation</div>
      $30/day answers <em>&ldquo;what does a qualified Panama-QIP lead cost in these markets, and does
      English or Arabic convert cheaper?&rdquo;</em> &mdash; not to deliver volume. <strong>Launch
      English-first across both countries</strong>, measure CPL, then scale and split per the
      milestones above. Make the scale-up decision around <strong>day ~21</strong>, judged on
      <strong>cost-per-qualified-lead</strong>, not click count.
    </div>
  </section>

  <!-- ============ 4. TOTALS ============ -->
  <section class="page-break">
    <div class="sec-head"><span class="sec-num">4</span><h2>Totals &amp; the CPC reality</h2></div>

    <h3>4.1 &nbsp;Total addressable volume (deduplicated &mdash; each unique keyword counted once)</h3>
    <table class="tbl-rec tbl-num" style="max-width:400px;">
      <thead><tr><th></th><th>English</th><th>Arabic</th><th>Total</th></tr></thead>
      <tbody>
        <tr><td><b>Oman</b></td><td>{TOTALS['EN_Oman']}</td><td>{TOTALS['AR_Oman']}</td><td><b>{TOTALS['Oman_total']}</b></td></tr>
        <tr><td><b>Jordan</b></td><td>{TOTALS['EN_Jordan']}</td><td>{TOTALS['AR_Jordan']}</td><td><b>{TOTALS['Jordan_total']}</b></td></tr>
        <tr><td><b>Total</b></td><td><b>{TOTALS['EN_total']}</b></td><td><b>{TOTALS['AR_total']}</b></td><td><b>{TOTALS['grand']} / mo</b></td></tr>
      </tbody>
    </table>
    <p>The market is <strong>English-weighted ({TOTALS['EN_total']} vs {TOTALS['AR_total']})</strong>
    and <strong>near-even between the two countries ({TOTALS['Oman_total']} Oman /
    {TOTALS['Jordan_total']} Jordan)</strong>. Exactly why the plan is English-first, both-countries,
    with Arabic layered in as budget scales.</p>

    <h3>4.2 &nbsp;The CPC reality</h3>
    <p>This is a <strong>premium-CPC category.</strong> Only <strong>4 keywords</strong> returned bid
    data (the volume-bearing head terms) &mdash; everything else has too little volume for Keyword
    Planner to report a bid:</p>
    <table class="tbl-rec tbl-num" style="max-width:420px;">
      <thead><tr><th>Bid tier</th><th>Range (USD)</th><th>Average</th></tr></thead>
      <tbody>
        <tr><td><b>Low top-of-page</b></td><td>$0.28 &ndash; $1.19</td><td><b>$0.61</b></td></tr>
        <tr><td><b>High top-of-page</b></td><td>$1.49 &ndash; $11.90</td><td><b>$5.13</b></td></tr>
      </tbody>
    </table>
    <p><em>golden visa</em> in <strong>Oman</strong> peaks at <strong>$11.90</strong> high-top-of-page
    &mdash; the single most expensive click in the set. <strong>Jordan CPCs are materially cheaper</strong>
    ($0.32&ndash;$2.11), one reason Arabic/Jordan-leaning traffic tends to be the cheaper click and
    worth testing as budget grows.</p>
    <div class="callout note">
      <div class="ct">Closing note</div>
      Every figure here is a Keyword Planner range &mdash; directional sizing, not a conversion
      guarantee. The real decisions &mdash; how much to scale, and whether English or Arabic converts
      cheaper &mdash; should be driven by the <strong>actual cost-per-qualified-lead</strong> observed
      in the first <strong>2&ndash;3 weeks</strong>, not by these pre-launch estimates.
    </div>
  </section>

  <!-- ============ 5. FULL KEYWORD TABLE ============ -->
  <section class="page-break">
    <div class="sec-head"><span class="sec-num">5</span><h2>All 121 researched keywords &mdash; full traffic table</h2></div>
    <p>Every researched keyword (73 English + 48 Arabic), <strong>sorted highest-volume first.</strong>
    Oman / Jordan columns show Keyword Planner&rsquo;s rounded monthly ranges;
    <span class="mut">&lt;10</span> means below the ~10 searches/month reporting floor. Arabic rows are
    shown right-to-left with transliteration and English gloss beneath. Only the four volume-bearing
    head terms (<span class="cpc-hi">highlighted CPC</span>) returned bid data; Panama money-terms are
    <span class="badge-money">PANAMA</span>-badged and shaded.</p>

    <div class="legend">
      <span><b>Legend:</b></span>
      <span><span class="lang lang-en">EN</span> English &middot; <span class="lang lang-ar">AR</span> Arabic</span>
      <span><span class="sw" style="background:#e5f1e8"></span>Low <span class="sw" style="background:#fdf1dd"></span>Med <span class="sw" style="background:#f9e4e2"></span>High competition</span>
      <span><span class="sw" style="background:#fbf6ea;border:1px solid #C79A3A"></span>Panama money-term row</span>
      <span><span class="cpc-hi">$0.00</span> = real CPC bid data</span>
    </div>

    <div class="kw-table-wrap">
      <table class="kw">
        <thead>
          <tr>
            <th>#</th>
            <th class="kwh">Keyword</th>
            <th>Lang</th>
            <th>Oman</th>
            <th>Jordan</th>
            <th>Comp.</th>
            <th>Est. CPC (USD)</th>
            <th>Priority</th>
          </tr>
        </thead>
        <tbody>
{KEYWORD_ROWS}
        </tbody>
      </table>
    </div>
  </section>

  <!-- ============ FOOTER ============ -->
  <footer class="foot">
    <b>Prepared by Mercan Group</b> &mdash; official Government-of-Panama partner for the Qualified
    Investor Program. This is a precision, high-value-per-lead campaign; success is measured in
    cost-per-qualified-lead, not clicks or impressions.
    <div class="prov-line">
      Data provenance: Google Keyword Planner (Google Ads API v23,
      KeywordPlanIdeaService.GenerateKeywordHistoricalMetrics) &middot; Oman + Jordan &middot;
      English + Arabic &middot; Google Search &middot; last 12 months. Volumes are rounded ranges
      (directional sizing, not a guarantee). &copy; 2026 Mercan Group &middot; internal operator brief.
    </div>
  </footer>

</div>
</body>
</html>
"""

with open(OUT_HTML, "w", encoding="utf-8") as fh:
    fh.write(HTML)

print("Wrote", OUT_HTML)
print("Keyword rows rendered:", len(ROWS))
print("Money-term keywords:", len(MONEY_KEYWORDS))
print("HTML bytes:", len(HTML.encode("utf-8")))
