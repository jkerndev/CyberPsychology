SELECT
  SUM(CASE WHEN is_ai = 1 THEN 1 ELSE 0 END) AS ai_count,
  SUM(CASE WHEN is_ai = 0 THEN 1 ELSE 0 END) AS non_ai_count
FROM participant_table;