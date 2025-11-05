/**
 * Doris Agent - Node.js 调用示例
 * 
 * 这是一个完整的 Node.js Agent 示例,展示如何通过 HTTP API 与 Doris 数据中台交互。
 * 
 * 使用前请确保:
 * 1. Doris 服务已启动: docker-compose up -d
 * 2. 安装依赖: npm install axios form-data
 */

const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

class DorisAgent {
  /**
   * 初始化 Doris Agent
   * @param {string} baseUrl - API 基础地址
   * @param {string} apiKey - DeepSeek API Key (可选)
   */
  constructor(baseUrl = 'http://localhost:8018', apiKey = null) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 60000,
    });
  }

  /**
   * 检查服务健康状态
   */
  async healthCheck() {
    const response = await this.client.get('/api/health');
    return response.data;
  }

  /**
   * 使用自然语言提问 (核心 Agent-to-Agent 接口)
   * @param {string} question - 自然语言问题
   * @param {string} apiKey - API Key (可选)
   * @param {string} model - 模型名称
   * @returns {Promise<Object>} 包含 SQL、查询结果和记录数
   * 
   * @example
   * const result = await agent.ask("2022年广东省有多少个机构?");
   * console.log('SQL:', result.sql);
   * console.log('结果:', result.data);
   */
  async ask(question, apiKey = null, model = 'deepseek-chat') {
    const payload = { query: question };
    
    const key = apiKey || this.apiKey;
    if (key) {
      payload.api_key = key;
      payload.model = model;
    }
    
    const response = await this.client.post('/api/query/natural', payload);
    return response.data;
  }

  /**
   * 上传 Excel 文件到 Doris
   * @param {string} filePath - Excel 文件路径
   * @param {string} tableName - 目标表名
   * @param {boolean} createTable - 是否自动创建表
   * @returns {Promise<Object>} 上传结果
   * 
   * @example
   * const result = await agent.uploadExcel('data.xlsx', 'institutions');
   * console.log(`导入了 ${result.rows_imported} 行数据`);
   */
  async uploadExcel(filePath, tableName, createTable = true) {
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));
    form.append('table_name', tableName);
    form.append('create_table', createTable.toString());

    const response = await this.client.post('/api/upload', form, {
      headers: form.getHeaders(),
    });
    return response.data;
  }

  /**
   * 预览 Excel 文件内容
   * @param {string} filePath - Excel 文件路径
   * @param {number} rows - 预览行数
   */
  async previewExcel(filePath, rows = 10) {
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));
    form.append('rows', rows.toString());

    const response = await this.client.post('/api/upload/preview', form, {
      headers: form.getHeaders(),
    });
    return response.data;
  }

  /**
   * 执行 SQL 查询
   * @param {string} sql - SQL 查询语句
   * @returns {Promise<Object>} 查询结果
   * 
   * @example
   * const result = await agent.query("SELECT * FROM institutions LIMIT 10");
   * result.data.forEach(row => console.log(row));
   */
  async query(sql) {
    const response = await this.client.post('/api/execute', {
      action: 'query',
      params: { sql },
    });
    return response.data;
  }

  /**
   * 获取所有表名
   */
  async getTables() {
    const response = await this.client.get('/api/tables');
    return response.data.tables;
  }

  /**
   * 获取表结构
   * @param {string} tableName - 表名
   */
  async getTableSchema(tableName) {
    const response = await this.client.get(`/api/tables/${tableName}/schema`);
    return response.data.schema;
  }

  /**
   * 创建 LLM 配置
   * @param {Object} config - 配置对象
   */
  async createLLMConfig(config) {
    const response = await this.client.post('/api/llm/config', config);
    return response.data;
  }
}

// ============ 示例用法 ============

async function main() {
  // 初始化 Agent (可选提供 API Key)
  const agent = new DorisAgent(
    'http://localhost:8018',
    'sk-748638f482f74b7392a6dafd89bdd307' // 替换为你的 API Key
  );

  console.log('='.repeat(60));
  console.log('Doris Agent 示例 (Node.js)');
  console.log('='.repeat(60));

  try {
    // 1. 健康检查
    console.log('\n1. 健康检查...');
    const health = await agent.healthCheck();
    console.log('✅ 服务状态:', health);

    // 2. 查看所有表
    console.log('\n2. 查看所有表...');
    const tables = await agent.getTables();
    console.log('📊 数据库中的表:', tables);

    // 3. 自然语言查询示例
    console.log('\n3. 自然语言查询示例...');
    const questions = [
      '有哪些表?',
      '统计每个表的记录数',
    ];

    for (const question of questions) {
      console.log(`\n❓ 问题: ${question}`);
      try {
        const result = await agent.ask(question);
        console.log(`📝 生成的 SQL:\n${result.sql}`);
        console.log(`📊 查询结果:`, result.data);
        console.log(`📈 记录数: ${result.count}`);
      } catch (error) {
        console.log(`❌ 查询失败:`, error.message);
      }
    }

    // 4. 直接 SQL 查询示例
    console.log('\n4. 直接 SQL 查询示例...');
    const result = await agent.query('SHOW DATABASES');
    console.log('📊 数据库列表:', result.data);

    // 5. Excel 上传示例 (如果有文件)
    console.log('\n5. Excel 上传示例...');
    console.log('💡 提示: 准备一个 Excel 文件,然后使用:');
    console.log("   const result = await agent.uploadExcel('data.xlsx', 'my_table');");

    console.log('\n' + '='.repeat(60));
    console.log('✅ 示例完成!');
    console.log('='.repeat(60));

  } catch (error) {
    console.error('❌ 错误:', error.message);
    if (error.response) {
      console.error('详细信息:', error.response.data);
    }
  }
}

// 运行示例
if (require.main === module) {
  main();
}

module.exports = DorisAgent;

