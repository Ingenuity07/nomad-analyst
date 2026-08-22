from django.contrib import admin
from .models import ResearchRun, Evidence, ResearchReport

@admin.register(ResearchRun)
class ResearchRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'research_type', 'status', 'created_at')
    list_filter = ('research_type', 'status')
    search_fields = ('query',)

@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ('title', 'source_type', 'source_name', 'retrieved_at')
    list_filter = ('source_type', 'source_name')
    search_fields = ('title', 'content')

@admin.register(ResearchReport)
class ResearchReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'research_run', 'created_at', 'updated_at')
    search_fields = ('title', 'summary', 'analysis')
