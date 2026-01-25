from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator

class Project(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, unique=True)
    description = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    companies: fields.ReverseRelation["Company"]
    invoice_projects: fields.ReverseRelation["InvoiceProject"]

    class Meta:
        table = "projects"

class Company(models.Model):
    id = fields.IntField(pk=True)
    project = fields.ForeignKeyField("models.Project", related_name="companies")
    name = fields.CharField(max_length=255)
    tax_id = fields.CharField(max_length=50, null=True)
    background_info = fields.TextField(null=True, description="Markdown content for company background")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    invoice_projects: fields.ReverseRelation["InvoiceProject"]

    class Meta:
        table = "companies"
        unique_together = (("project", "name"),)

class InvoiceProject(models.Model):
    id = fields.IntField(pk=True)
    project = fields.ForeignKeyField("models.Project", related_name="invoice_projects")
    company = fields.ForeignKeyField("models.Company", related_name="invoice_projects")
    name = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    sales_raw_table = fields.CharField(max_length=255, null=True)
    purchase_raw_table = fields.CharField(max_length=255, null=True)
    derived_table_1 = fields.CharField(max_length=255, null=True)
    derived_table_2 = fields.CharField(max_length=255, null=True)
    derived_table_3 = fields.CharField(max_length=255, null=True)
    derived_table_4 = fields.CharField(max_length=255, null=True)
    derived_table_5 = fields.CharField(max_length=255, null=True)
    sales_uploaded_at = fields.DatetimeField(null=True)
    purchase_uploaded_at = fields.DatetimeField(null=True)
    derived_generated_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "invoice_projects"
        unique_together = (("company", "name"),)

class InvoiceUpload(models.Model):
    id = fields.IntField(pk=True)
    invoice_project = fields.ForeignKeyField("models.InvoiceProject", related_name="uploads")
    direction = fields.CharField(max_length=20)
    filename = fields.CharField(max_length=255)
    file_size = fields.BigIntField(null=True)
    row_count = fields.IntField(null=True)
    status = fields.CharField(max_length=20, default="success")
    error_message = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "invoice_uploads"
        unique_together = (("invoice_project", "direction", "filename"),)



class ProjectLLMConfig(models.Model):
    id = fields.IntField(pk=True)
    project = fields.ForeignKeyField("models.Project", related_name="llm_configs")
    provider_type = fields.CharField(max_length=50)
    endpoint = fields.CharField(max_length=500)
    model_name = fields.CharField(max_length=200)
    api_key = fields.CharField(max_length=500, null=True)
    temperature = fields.FloatField(null=True)
    max_tokens = fields.IntField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "project_llm_configs"
        unique_together = (("project",),)


class ProjectAgentPrompt(models.Model):
    id = fields.IntField(pk=True)
    project = fields.ForeignKeyField("models.Project", related_name="agent_prompts")
    prompt = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "project_agent_prompts"
        unique_together = (("project",),)


class ChatSession(models.Model):
    """聊天会话 - 类似GPT的对话"""
    id = fields.IntField(pk=True)
    project = fields.ForeignKeyField("models.Project", related_name="chat_sessions")
    company = fields.ForeignKeyField("models.Company", related_name="chat_sessions", null=True)
    title = fields.CharField(max_length=255, default="新对话")
    summary = fields.TextField(null=True, description="会话摘要，用于上下文压缩")
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    messages: fields.ReverseRelation["ChatMessage"]

    class Meta:
        table = "chat_sessions"


class ChatMessage(models.Model):
    """聊天消息"""
    id = fields.IntField(pk=True)
    session = fields.ForeignKeyField("models.ChatSession", related_name="messages")
    role = fields.CharField(max_length=20)  # user, assistant, system
    content = fields.TextField()
    sql = fields.TextField(null=True, description="执行的SQL（如果有）")
    widget = fields.JSONField(null=True, description="附带的widget数据")
    token_count = fields.IntField(null=True, description="消息token数估算")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_messages"
# Pydantic models for API
Project_Pydantic = pydantic_model_creator(Project, name="Project")
ProjectIn_Pydantic = pydantic_model_creator(Project, name="ProjectIn", exclude_readonly=True)

Company_Pydantic = pydantic_model_creator(Company, name="Company")
CompanyIn_Pydantic = pydantic_model_creator(Company, name="CompanyIn", exclude_readonly=True)

InvoiceProject_Pydantic = pydantic_model_creator(InvoiceProject, name="InvoiceProject")
InvoiceProjectIn_Pydantic = pydantic_model_creator(InvoiceProject, name="InvoiceProjectIn", exclude_readonly=True)

InvoiceUpload_Pydantic = pydantic_model_creator(InvoiceUpload, name="InvoiceUpload")

ProjectLLMConfig_Pydantic = pydantic_model_creator(ProjectLLMConfig, name="ProjectLLMConfig")
ProjectLLMConfigIn_Pydantic = pydantic_model_creator(ProjectLLMConfig, name="ProjectLLMConfigIn", exclude_readonly=True)

ProjectAgentPrompt_Pydantic = pydantic_model_creator(ProjectAgentPrompt, name="ProjectAgentPrompt")
ProjectAgentPromptIn_Pydantic = pydantic_model_creator(ProjectAgentPrompt, name="ProjectAgentPromptIn", exclude_readonly=True)

ChatSession_Pydantic = pydantic_model_creator(ChatSession, name="ChatSession")
ChatSessionIn_Pydantic = pydantic_model_creator(ChatSession, name="ChatSessionIn", exclude_readonly=True)

ChatMessage_Pydantic = pydantic_model_creator(ChatMessage, name="ChatMessage")
ChatMessageIn_Pydantic = pydantic_model_creator(ChatMessage, name="ChatMessageIn", exclude_readonly=True)
