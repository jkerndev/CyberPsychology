import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

# ——— 1. Connect to the database ———
DB_PATH = "PIIsurvey/instance/database.db"
conn = sqlite3.connect(DB_PATH)

# ——— 2. Run the queries ———
# total participants
df_total = pd.read_sql_query(
    "SELECT COUNT(*) AS total_participants FROM participant_table", 
    conn
)

# total by major
df_by_major = pd.read_sql_query(
    """
    SELECT major, COUNT(*) AS count
    FROM participant_table
    GROUP BY major
    ORDER BY count DESC
    """,
    conn
)

# total by major and survey variant
df_by_major_variant = pd.read_sql_query(
    """
    SELECT major, 
           CASE WHEN is_ai=1 THEN 'AI' ELSE 'Non-AI' END AS variant,
           COUNT(*) AS count
    FROM participant_table
    GROUP BY major, is_ai
    ORDER BY major, variant
    """,
    conn
)

conn.close()

# ——— 3. Print the tables ———
print("\nTOTAL PARTICIPANTS")
print(df_total.to_string(index=False))

print("\nPARTICIPANTS BY MAJOR")
print(df_by_major.to_string(index=False))

print("\nPARTICIPANTS BY MAJOR & SURVEY VARIANT")
print(df_by_major_variant.to_string(index=False))

# ——— 4. Visualize ———
plt.figure(figsize=(8,4))
df_by_major.plot.bar(x='major', y='count', legend=False)
plt.title("Total Participants by Major")
plt.ylabel("Count")
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.show()

plt.figure(figsize=(8,4))
pivot = df_by_major_variant.pivot(index='major', columns='variant', values='count').fillna(0)
pivot.plot.bar()
plt.title("Participants by Major & Survey Variant")
plt.ylabel("Count")
plt.xticks(rotation=45, ha='right')
plt.legend(title="Variant")
plt.tight_layout()
plt.show()
