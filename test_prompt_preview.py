"""
测试脚本 - 预览生成的 Prompt

这个脚本展示当用户问 "来自广州的机构有多少个?" 时,
系统会生成什么样的 Prompt 发送给大模型。
"""

# 模拟的 Prompt 示例
def show_prompt_example():
    prompt = """You are an expert SQL query generator for Apache Doris database.

================================================================================
IMPORTANT: Your goal is to generate SQL that ACTUALLY RETURNS DATA.
================================================================================

# 1. Database Schema

CREATE TABLE `institutions` (
  `id` INT NOT NULL,
  `name` VARCHAR(255) NULL,
  `province` VARCHAR(50) NULL,
  `city` VARCHAR(50) NULL,
  `year` INT NULL
) ENGINE=OLAP
UNIQUE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 10;

# 2. Sample Data (ACTUAL VALUES from database)

**CRITICAL**: Use these actual values to understand the data format!

Table: `institutions`
Sample rows:
  Row 1: {'id': 1, 'name': '广州科技有限公司', 'province': '广东省', 'city': '广州市', 'year': 2022}
  Row 2: {'id': 2, 'name': '深圳创新企业', 'province': '广东省', 'city': '深圳市', 'year': 2022}
  Row 3: {'id': 3, 'name': '北京智能科技', 'province': '北京市', 'city': '北京市', 'year': 2021}

  Column `province` contains these ACTUAL values:
  ['广东省', '北京市', '上海市', '浙江省', '江苏省', '四川省']

  Column `city` contains these ACTUAL values:
  ['广州市', '深圳市', '北京市', '上海市', '杭州市', '南京市', '成都市', '东莞市', '佛山市', '珠海市']

# 5. Your Task

Question: 来自广州的机构有多少个?

# 6. Critical Instructions

**READ THE SAMPLE DATA ABOVE CAREFULLY!**

Rules:
1. Generate ONLY the SQL query, no explanations or comments
2. Use backticks for Chinese column/table names: `城市`, `省份`
3. The SQL MUST be executable in Apache Doris
4. Do NOT use markdown code blocks (no ```sql)
5. Return ONLY the raw SQL statement

**FUZZY MATCHING RULES** (MOST IMPORTANT):
- If the question mentions a location (city/province), CHECK the sample data above
- If sample data shows '广州市' but question asks '广州', use: WHERE column LIKE '%广州%'
- If sample data shows '北京市' but question asks '北京', use: WHERE column LIKE '%北京%'
- ALWAYS use LIKE '%keyword%' for location searches unless you see an EXACT match in sample data
- For numeric comparisons (year, count, etc.), use exact match (=, >, <)
- For text searches (names, locations), prefer LIKE '%keyword%' for better recall

**EXAMPLES**:
- Question: '来自广州的机构' + Sample data has '广州市' → WHERE `城市` LIKE '%广州%'
- Question: '2022年的数据' → WHERE `年份` = 2022
- Question: '包含科技的公司' → WHERE `公司名` LIKE '%科技%'

Now generate the SQL query:

SQL:"""
    
    return prompt


def show_expected_output():
    """展示期望的 SQL 输出"""
    return "SELECT COUNT(*) as count FROM `institutions` WHERE `city` LIKE '%广州%'"


if __name__ == "__main__":
    print("=" * 100)
    print("智能 Prompt 预览")
    print("=" * 100)
    print("\n用户问题: 来自广州的机构有多少个?\n")
    print("=" * 100)
    print("发送给大模型的 Prompt:")
    print("=" * 100)
    print(show_prompt_example())
    print("\n" + "=" * 100)
    print("期望的 SQL 输出:")
    print("=" * 100)
    print(show_expected_output())
    print("\n" + "=" * 100)
    print("关键改进点:")
    print("=" * 100)
    print("✅ 1. 提供了实际的样本数据 (看到 '广州市' 而不是 '广州')")
    print("✅ 2. 提供了列的所有可能值 (city 列包含 '广州市', '深圳市' 等)")
    print("✅ 3. 明确指示使用 LIKE '%广州%' 进行模糊匹配")
    print("✅ 4. 给出了具体的示例说明")
    print("✅ 5. 强调了 '广州' 应该匹配 '广州市'")
    print("=" * 100)

