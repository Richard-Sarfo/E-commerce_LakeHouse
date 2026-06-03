"""
Generates the P2 Lakehouse architecture diagram as a PNG.

Run:
    python scripts/generate_architecture_diagram.py
Output:
    docs/architecture.png
"""

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ── Palette ────────────────────────────────────────────────────────────────
C = {
    "s3":          "#3E8A2F",
    "glue":        "#8B2FC9",
    "sfn":         "#C7166A",
    "eventbridge": "#C7166A",
    "athena":      "#1A73E8",
    "delta":       "#007B9E",
    "sns":         "#C0392B",
    "github":      "#24292E",
    "local":       "#4A5568",
    "iam":         "#B03030",
    "catalog":     "#1A7A45",
    "aws_dark":    "#1A202C",
    "orange":      "#E07B00",
    "bg":          "#F7F8FA",
    "rejected":    "#C05A10",
}

FIG_W, FIG_H = 22, 15


def box(ax, x, y, w, h, label, sublabel="",
        color="#569A31", fontsize=8.5, text_color="#FFFFFF", radius=0.25):
    rect = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.04,rounding_size={radius}",
        linewidth=1.4, edgecolor=_darken(color), facecolor=color, zorder=3,
    )
    ax.add_patch(rect)
    ty = y + h / 2 + (0.13 if sublabel else 0)
    ax.text(x + w / 2, ty, label, ha="center", va="center",
            fontsize=fontsize, fontweight="bold", color=text_color, zorder=4)
    if sublabel:
        ax.text(x + w / 2, y + h / 2 - 0.19, sublabel, ha="center", va="center",
                fontsize=6.8, color=text_color, zorder=4, alpha=0.92)


def _darken(hex_color, factor=0.72):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(int(r*factor), int(g*factor), int(b*factor))


def section(ax, x, y, w, h, label, color="#FAFAFA", lc="#BBBBBB"):
    rect = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.1,rounding_size=0.4",
        linewidth=1.8, edgecolor=lc, facecolor=color, zorder=1,
    )
    ax.add_patch(rect)
    ax.text(x + 0.2, y + h - 0.2, label, ha="left", va="top",
            fontsize=8, color=lc, fontstyle="italic", fontweight="bold", zorder=2)


def arr(ax, x1, y1, x2, y2, color="#555555", lw=1.6, rad=0.0, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw,
                                connectionstyle=f"arc3,rad={rad}"), zorder=5)
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my+0.13, label, ha="center", va="bottom",
                fontsize=6.5, color=color, zorder=6,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1))


def main():
    Path("docs").mkdir(exist_ok=True)

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_xlim(0, FIG_W)
    ax.set_ylim(0, FIG_H)
    ax.axis("off")

    # ── Title ──────────────────────────────────────────────────────────────
    ax.text(FIG_W/2, FIG_H - 0.35, "Lakehouse Architecture — E-Commerce Transactions",
            ha="center", va="top", fontsize=17, fontweight="bold", color=C["aws_dark"])
    ax.text(FIG_W/2, FIG_H - 0.78,
            "AWS Glue + Delta Lake  ·  Step Functions  ·  Athena  ·  GitHub Actions CI/CD",
            ha="center", va="top", fontsize=9, color="#666666")

    # ══════════════════════════════════════════════════════════
    # COL 1  Local (x 0.3–3.7)
    # ══════════════════════════════════════════════════════════
    section(ax, 0.3, 9.7, 3.4, 3.9, "Local", color="#EDEEF2", lc=C["local"])

    box(ax, 0.55, 12.7, 2.9, 0.65, "Source Files",
        "orders.xlsx · order_items.xlsx · products.csv",
        color=C["local"], fontsize=8)
    box(ax, 0.55, 11.8, 2.9, 0.65, "convert_xlsx_to_csv.py",
        "pandas + openpyxl → UTF-8 CSV",
        color=C["local"], fontsize=8)
    box(ax, 0.55, 10.9, 2.9, 0.65, "upload_raw.py",
        "boto3 → S3 raw/{dataset}/",
        color=C["local"], fontsize=8)

    arr(ax, 2.0, 12.7, 2.0, 12.45, color=C["local"])
    arr(ax, 2.0, 11.8, 2.0, 11.55, color=C["local"])

    # ══════════════════════════════════════════════════════════
    # COL 2  S3 Raw + EventBridge (x 4.0–8.2)
    # ══════════════════════════════════════════════════════════
    section(ax, 4.0, 9.7, 4.2, 3.9, "S3 Raw Zone + Trigger", color="#FFF8EE", lc=C["s3"])

    box(ax, 4.25, 12.65, 1.7, 0.65, "raw/products/",   "", color=C["s3"], fontsize=8)
    box(ax, 6.15, 12.65, 1.7, 0.65, "raw/orders/",     "", color=C["s3"], fontsize=8)
    box(ax, 4.25, 11.8,  3.6, 0.65, "raw/order_items/","", color=C["s3"], fontsize=8)

    box(ax, 4.25, 10.85, 3.6, 0.7, "Amazon S3",
        "Versioning · AES-256 · EventBridge enabled",
        color=C["s3"], fontsize=8)
    box(ax, 4.25, 9.9, 3.6, 0.7, "Amazon EventBridge",
        "Object Created rule → raw/* prefix",
        color=C["eventbridge"], fontsize=8)

    arr(ax, 3.45, 11.22, 4.25, 11.22, color=C["s3"], label="upload")
    arr(ax, 7.0, 12.65, 7.0, 12.45, color=C["s3"])
    arr(ax, 5.1, 12.65, 5.1, 12.45, color=C["s3"])
    arr(ax, 6.05, 11.8, 6.05, 11.55, color=C["s3"])
    arr(ax, 6.05, 10.85, 6.05, 10.62, color=C["eventbridge"])

    # ══════════════════════════════════════════════════════════
    # COL 3  Step Functions  (x 8.5–15.5)
    # ══════════════════════════════════════════════════════════
    section(ax, 8.5, 7.3, 7.2, 6.3, "Step Functions Orchestration", color="#FEF0F8", lc=C["sfn"])

    box(ax, 8.75, 12.7, 6.7, 0.65, "AWS Step Functions  —  ETL Lifecycle Pipeline",
        "1-hour overall timeout · execution logs → CloudWatch",
        color=C["sfn"], fontsize=9)

    # parallel label
    ax.text(12.1, 12.15, "── Parallel State ──", ha="center", va="center",
            fontsize=7.5, color=C["sfn"], fontstyle="italic")

    box(ax, 8.75, 11.2, 3.0, 0.75, "Glue: transform_dataset",
        "--dataset products", color=C["glue"], fontsize=8)
    box(ax, 12.45, 11.2, 3.0, 0.75, "Glue: transform_dataset",
        "--dataset orders", color=C["glue"], fontsize=8)

    box(ax, 10.0, 10.1, 4.2, 0.75, "Glue: transform_dataset",
        "--dataset order_items  (RI: refs products + orders)",
        color=C["glue"], fontsize=8)
    box(ax, 10.0, 9.0, 4.2, 0.75, "Glue: archive_files.py",
        "copy raw/ → archived/<dataset>/<YYYY-MM-DD>/  then delete",
        color=C["glue"], fontsize=8)
    box(ax, 10.0, 7.9, 4.2, 0.75, "Athena Validation Query",
        "SELECT COUNT(*) per table → confirms data presence",
        color=C["athena"], fontsize=8)

    # SFN internal flow arrows
    arr(ax, 7.85, 10.25, 8.75, 11.57, color=C["sfn"])     # EB → products
    arr(ax, 7.85, 10.25, 12.45, 11.57, color=C["sfn"])    # EB → orders
    arr(ax, 10.25, 11.2, 10.25, 10.85, color=C["sfn"])    # products → order_items
    arr(ax, 13.95, 11.2, 13.95, 10.85, color=C["sfn"])    # orders → order_items
    arr(ax, 12.1, 10.1, 12.1, 9.75, color=C["sfn"])
    arr(ax, 12.1, 9.0, 12.1, 8.65, color=C["sfn"])

    # EventBridge → SFN
    arr(ax, 7.85, 9.9, 8.75, 12.72, color=C["sfn"], label="StartExecution")

    # ── Failure path (right side) ───────────────────────────────────────
    box(ax, 16.0, 11.1, 2.7, 0.75, "Amazon SNS",
        "Failure alert email", color=C["sns"], fontsize=8)
    box(ax, 16.0, 10.1, 2.7, 0.65, "Fail State",
        "Execution ends FAILED", color=C["aws_dark"], fontsize=8)

    arr(ax, 13.5, 11.57, 16.0, 11.47, color=C["sns"], label="Catch: ALL")
    arr(ax, 17.35, 11.1, 17.35, 10.75, color=C["sns"])

    # ══════════════════════════════════════════════════════════
    # ROW B  Delta Zone (x 0.3–10.8,  y 4.5–7.1)
    # ══════════════════════════════════════════════════════════
    section(ax, 0.3, 4.5, 10.5, 4.6, "Processed Zone  —  Delta Lake (S3)", color="#EDF8F2", lc=C["delta"])

    box(ax, 0.55, 7.55, 3.0, 1.1, "delta: products",
        "PK: product_id\nno partition  (small dimension)",
        color=C["delta"], fontsize=8)
    box(ax, 3.8, 7.55, 3.0, 1.1, "delta: orders",
        "PK: order_id\npartition: date",
        color=C["delta"], fontsize=8)
    box(ax, 7.05, 7.55, 3.0, 1.1, "delta: order_items",
        "PK: id\npartition: date",
        color=C["delta"], fontsize=8)

    box(ax, 0.55, 6.4, 9.5, 0.85,
        "ACID Transactions  ·  Schema Enforcement  ·  MERGE / Upsert  ·  Time Travel  ·  _delta_log",
        "", color=C["delta"], fontsize=8.5, radius=0.22)

    box(ax, 0.55, 5.3, 4.5, 0.85, "rejected/<dataset>/run=<exec_id>/",
        "Parquet  ·  _reject_reason column  ·  auditable",
        color=C["rejected"], fontsize=8)

    box(ax, 5.35, 5.3, 4.7, 0.85, "archived/<dataset>/YYYY-MM-DD/",
        "Original CSVs moved here after successful load",
        color=C["s3"], fontsize=8)

    # Glue → Delta arrows
    arr(ax, 9.25, 11.57, 2.05, 8.65, color=C["glue"], rad=0.15)
    arr(ax, 12.1, 10.1,  5.3,  8.65, color=C["glue"], rad=0.1)
    arr(ax, 14.2, 10.1,  8.55, 8.65, color=C["glue"], rad=-0.08)

    # Archive job → archived prefix
    arr(ax, 8.05, 9.0, 7.7, 6.15, color=C["s3"], rad=-0.25, label="archive")

    # Rejected rows from Glue
    arr(ax, 9.5, 10.48, 2.8, 6.15, color=C["rejected"], rad=0.12, label="rejected rows")

    # ══════════════════════════════════════════════════════════
    # ROW B right  Analytics (x 11.0–18.5,  y 4.5–7.1)
    # ══════════════════════════════════════════════════════════
    section(ax, 11.0, 4.5, 7.5, 4.6, "Analytics Layer", color="#EEF4FF", lc=C["athena"])

    box(ax, 11.25, 7.5, 3.0, 1.2, "Glue Data Catalog",
        "table_type=DELTA\nspark.sql.sources.provider=delta\nexplicit schemas in Terraform",
        color=C["catalog"], fontsize=8)

    box(ax, 14.75, 7.5, 3.0, 1.2, "Amazon Athena",
        "Engine v3 · native Delta reads\nSSE-S3 results · dedicated workgroup",
        color=C["athena"], fontsize=8)

    box(ax, 11.25, 6.1, 6.5, 1.05,
        "Sample Analytics Queries",
        "daily revenue · top products by dept · reorder rate · row-count validation",
        color=C["athena"], fontsize=8.5)

    box(ax, 11.25, 4.9, 6.5, 0.9,
        "Analysts / BI Tools",
        "Athena console  ·  AWS SDK  ·  JDBC / ODBC",
        color=C["aws_dark"], fontsize=8.5)

    # Delta → Catalog
    arr(ax, 10.05, 8.1, 11.25, 8.1, color=C["catalog"], label="registered tables")
    # Catalog → Athena
    arr(ax, 14.25, 8.1, 14.75, 8.1, color=C["athena"])
    # Athena → queries
    arr(ax, 16.25, 7.5, 14.5, 7.15, color=C["athena"])
    arr(ax, 14.5, 6.1, 14.5, 5.8, color=C["athena"])

    # SFN Athena validation → Athena service
    arr(ax, 14.2, 8.27, 14.75, 8.27, color=C["athena"], rad=-0.4, label="validate")

    # ══════════════════════════════════════════════════════════
    # ROW C  CI/CD (y 0.3–4.2)
    # ══════════════════════════════════════════════════════════
    section(ax, 0.3, 0.25, 21.3, 4.0, "CI/CD  —  GitHub Actions", color="#F3F3F3", lc=C["github"])

    # Workflow boxes
    box(ax, 0.6, 2.9, 4.5, 1.1, "ci.yml  (all branches + PRs)",
        "ruff lint  ·  pytest (local Spark, no AWS)\nterraform fmt -check  +  terraform validate",
        color=C["github"], fontsize=8.5)
    box(ax, 5.5, 2.9, 4.5, 1.1, "deploy.yml  (main only)",
        "OIDC → AWS  ·  terraform apply\naws s3 sync glue_jobs/ → S3 scripts",
        color=C["github"], fontsize=8.5)
    box(ax, 10.4, 2.9, 4.0, 1.1, "GitHub OIDC Role (IAM)",
        "Scoped to refs/heads/main\nNo long-lived access keys in secrets",
        color=C["iam"], fontsize=8.5)
    box(ax, 14.8, 2.9, 4.5, 1.1, "Secrets",
        "AWS_ROLE_TO_ASSUME · AWS_REGION\nTF_STATE_BUCKET · ALERT_EMAIL",
        color="#555555", fontsize=8.5)

    box(ax, 0.6, 0.55, 4.5, 2.05,
        "Unit Test Coverage",
        "test_validation.py\n  null PK · bad timestamp\n  negative values · dedup order\ntest_delta_io.py\n  initial write · MERGE update\n  insert new row · partition",
        color=C["local"], fontsize=8)

    box(ax, 5.5, 0.55, 4.5, 2.05,
        "Resources Provisioned",
        "S3 bucket · IAM roles\nGlue jobs (transform + archive)\nGlue Catalog tables\nStep Functions · EventBridge\nSNS topic · Athena workgroup",
        color=C["orange"], text_color=C["aws_dark"], fontsize=8)

    box(ax, 10.4, 0.55, 4.0, 2.05,
        "Terraform Backend",
        "Remote state in S3\nPlan in CI · Apply on merge\nterraform fmt enforced in CI",
        color="#4A5568", fontsize=8)

    box(ax, 14.8, 0.55, 4.5, 2.05,
        "Deployment Flow",
        "PR → ci.yml validates\nMerge to main → deploy.yml\nterraform output → bucket name\nScript sync belt-and-braces",
        color=C["aws_dark"], fontsize=8)

    arr(ax, 5.1, 3.45, 5.5, 3.45, color=C["github"])
    arr(ax, 10.0, 3.45, 10.4, 3.45, color=C["github"])
    arr(ax, 14.4, 3.45, 14.8, 3.45, color=C["github"])

    # deploy → infra
    arr(ax, 7.75, 2.9, 7.75, 7.55, color=C["github"], rad=-0.35, label="deploys infra on push to main")

    # ── Legend ─────────────────────────────────────────────────────────────
    items = [
        (C["s3"],          "Amazon S3"),
        (C["glue"],        "AWS Glue + Spark"),
        (C["delta"],       "Delta Lake"),
        (C["sfn"],         "Step Functions / EventBridge"),
        (C["athena"],      "Amazon Athena"),
        (C["catalog"],     "Glue Data Catalog"),
        (C["sns"],         "Amazon SNS"),
        (C["github"],      "GitHub Actions"),
        (C["local"],       "Local tooling"),
        (C["rejected"],    "Rejection path"),
    ]
    patches = [mpatches.Patch(color=c, label=l) for c, l in items]
    ax.legend(handles=patches, loc="lower right", bbox_to_anchor=(0.999, 0.002),
              ncol=2, fontsize=7.5, framealpha=0.95,
              title="Service legend", title_fontsize=8)

    plt.tight_layout(pad=0.2)
    out = Path("docs") / "architecture.png"
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    print(f"Saved: {out.resolve()}")


if __name__ == "__main__":
    main()
