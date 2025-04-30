import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

# ——— 1. Load & de-duplicate ———
DB = "PIIsurvey/instance/database.db"
conn = sqlite3.connect(DB)

query = """
SELECT
  r.participant_id,
  p.is_ai,
  r.question_id,
  r.answered,
  r.skipped
FROM response_table r
JOIN (
    SELECT MIN(id) AS keep_id
    FROM response_table
    GROUP BY participant_id, question_id
) AS first_rows ON r.id = first_rows.keep_id
JOIN participant_table p ON r.participant_id = p.id
"""
df = pd.read_sql_query(query, conn)
conn.close()

# ——— 2. Map questions to PII category & variant ———
category_map = {
    1:"age",11:"age",
    2:"biological sex",12:"biological sex",
    3:"time online/week",13:"time online/week",
    4:"name",14:"name",
    5:"race/ethnicity",15:"race/ethnicity",
    6:"personal email",16:"personal email",
    7:"postal address",17:"postal address",
    8:"phone number",18:"phone number",
    9:"SSN",19:"SSN",
}
df["category"] = df["question_id"].map(category_map)
df["variant"]  = df["is_ai"].map({0:"Non-AI", 1:"AI"})

# ——— 3. Count participants per variant & overall ———
participants = df[["participant_id","variant"]].drop_duplicates()
counts = participants["variant"].value_counts().to_dict()
counts["Total"] = participants["participant_id"].nunique()

# ——— 4. Proportion answered per category & variant ———
ans = (
    df[df.answered==1]
      .groupby(["category","variant"]) 
      .size() 
      .unstack(fill_value=0)
)
# add missing columns if one variant has no answers for a category
for v in ("Non-AI","AI"):
    if v not in ans.columns:
        ans[v] = 0
ans["Total"] = ans.sum(axis=1)

# convert to proportions
ans_prop = ans.copy()
ans_prop["Non-AI"] /= counts["Non-AI"]
ans_prop["AI"]     /= counts["AI"]
ans_prop["Total"]  /= counts["Total"]

# ——— 5. Proportion skipped per category & variant ———
skp = (
    df[df.skipped==1]
      .groupby(["category","variant"])
      .size()
      .unstack(fill_value=0)
)
for v in ("Non-AI","AI"):
    if v not in skp.columns:
        skp[v] = 0
skp["Total"] = skp.sum(axis=1)

skp_prop = skp.copy()
skp_prop["Non-AI"] /= counts["Non-AI"]
skp_prop["AI"]     /= counts["AI"]
skp_prop["Total"]  /= counts["Total"]

# ——— 6. Per‐participant answered counts & summary stats ———
per_part = (
    df.pivot_table(index="participant_id",
                   columns="variant",
                   values="answered",
                   aggfunc="sum",
                   fill_value=0)
)
# ensure both columns exist
for v in ("Non-AI","AI"):
    if v not in per_part:
        per_part[v] = 0
per_part["Overall"] = per_part["Non-AI"] + per_part["AI"]

stats = {
    name: {
        "mean": per_part[name].mean(),
        "std":  per_part[name].std()
    }
    for name in ["Overall","Non-AI","AI"]
}

# ——— 7. Print results ———
pd.set_option("display.precision", 3)
print("\n% Answered per PII category (proportions):")
print(ans_prop)

print("\n% Skipped per PII category (proportions):")
print(skp_prop)

print("\nAnswered‐count summary per participant:")
for grp, vals in stats.items():
    print(f"  {grp:7}: mean = {vals['mean']:.2f},  std = {vals['std']:.2f}")

# ——— 8. Plot answered proportions ———
plt.figure(figsize=(10,6))
ans_prop[["Non-AI","AI","Total"]].plot(
    kind="bar", rot=45, xlabel="PII Category", ylabel="Proportion of participants"
)
plt.title("Proportion of Participants Who Answered, by PII Category & Variant")
plt.legend(title="Survey Variant")
plt.tight_layout()
plt.show()

# ——— 9. Plot skipped proportions ———
plt.figure(figsize=(10,6))
skp_prop[["Non-AI","AI","Total"]].plot(
    kind="bar", rot=45, xlabel="PII Category", ylabel="Proportion of participants"
)
plt.title("Proportion of Participants Who Skipped, by PII Category & Variant")
plt.legend(title="Survey Variant")
plt.tight_layout()
plt.show()
