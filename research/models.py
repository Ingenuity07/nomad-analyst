import uuid
import hashlib
from django.db import models

class ResearchRun(models.Model):
    STATUS_CHOICES = (
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    research_type = models.CharField(max_length=50, default='ON_DEMAND') # e.g. ON_DEMAND, COMPANY_RESEARCH, SECTOR_RESEARCH
    research_mode = models.CharField(max_length=30, default='INTRADAY', db_index=True) # INTRADAY, LONG_TERM, GENERAL
    symbol = models.CharField(max_length=50, blank=True, db_index=True)
    instrument = models.ForeignKey('market.Instrument', on_delete=models.SET_NULL, null=True, blank=True, related_name='research_runs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    query = models.TextField(blank=True)
    
    # Evidence snapshot & hash
    evidence_snapshot = models.JSONField(default=dict, blank=True)
    evidence_hash = models.CharField(max_length=64, blank=True, db_index=True)
    
    # Structured research report output
    research_output = models.JSONField(default=dict, blank=True)
    
    # Model and provenance metadata
    model_name = models.CharField(max_length=100, blank=True)
    provider = models.CharField(max_length=50, blank=True)
    model_version = models.CharField(max_length=50, blank=True)
    
    # Snapshots at analysis time for deterministic delta calculation
    opportunity_score_at_research = models.FloatField(null=True, blank=True)
    opportunity_state_at_research = models.CharField(max_length=50, blank=True)
    market_context_snapshot = models.JSONField(default=dict, blank=True)
    
    # Performance and cost telemetry
    tokens_used = models.IntegerField(default=0)
    duration_ms = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    error_category = models.CharField(max_length=100, blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['symbol', 'research_mode', '-started_at']),
        ]

    def __str__(self):
        return f"ResearchRun {self.symbol or self.research_type} [{self.research_mode}] - {self.status} ({self.id})"


class Evidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    research_run = models.ForeignKey(ResearchRun, on_delete=models.CASCADE, related_name='evidence')
    source_type = models.CharField(max_length=50) # e.g. web, file, api
    source_name = models.CharField(max_length=255) # e.g. yfinance, moneycontrol
    source_url = models.URLField(max_length=1000, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    content = models.TextField()
    published_at = models.DateTimeField(blank=True, null=True)
    retrieved_at = models.DateTimeField(auto_now_add=True)
    content_hash = models.CharField(max_length=64, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        # Auto-compute SHA-256 content hash on save if not provided
        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(self.content.encode('utf-8')).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Evidence {self.source_type}:{self.source_name} ({self.title or str(self.id)[:8]})"


class ResearchReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    research_run = models.ForeignKey(ResearchRun, on_delete=models.CASCADE, related_name='reports')
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True, null=True)
    analysis = models.TextField() # markdown content
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
