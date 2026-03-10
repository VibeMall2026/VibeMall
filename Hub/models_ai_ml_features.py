"""
AI/ML Features Models - Phase 11
Features: Product Recommendation Engine, Dynamic Pricing, Demand Forecasting, Fraud Detection, Chatbot, Image Search
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json


class RecommendationEngine(models.Model):
    """Product recommendation engine configuration"""
    ALGORITHM_CHOICES = [
        ('COLLABORATIVE_FILTERING', 'Collaborative Filtering'),
        ('CONTENT_BASED', 'Content-Based Filtering'),
        ('HYBRID', 'Hybrid Approach'),
        ('MATRIX_FACTORIZATION', 'Matrix Factorization'),
        ('DEEP_LEARNING', 'Deep Learning'),
        ('ASSOCIATION_RULES', 'Association Rules'),
    ]
    
    STATUS_CHOICES = [
        ('TRAINING', 'Training'),
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('FAILED', 'Failed'),
    ]
    
    name = models.CharField(max_length=100)
    algorithm = models.CharField(max_length=30, choices=ALGORITHM_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TRAINING')
    
    # Model configuration
    model_parameters = models.JSONField(default=dict, help_text="Algorithm-specific parameters")
    training_data_size = models.PositiveIntegerField(default=0)
    
    # Performance metrics
    accuracy_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    precision_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    recall_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    f1_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    
    # Business metrics
    click_through_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    revenue_impact = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Training information
    last_trained = models.DateTimeField(null=True, blank=True)
    training_duration_minutes = models.PositiveIntegerField(default=0)
    
    # Model files
    model_file_path = models.CharField(max_length=500, blank=True)
    model_version = models.CharField(max_length=20, default='1.0')
    
    # Settings
    is_active = models.BooleanField(default=False)
    auto_retrain = models.BooleanField(default=True)
    retrain_frequency_days = models.PositiveIntegerField(default=7)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_algorithm_display()}) - {self.status}"


class ProductRecommendation(models.Model):
    """Individual product recommendations"""
    RECOMMENDATION_TYPE_CHOICES = [
        ('PERSONALIZED', 'Personalized Recommendations'),
        ('SIMILAR_PRODUCTS', 'Similar Products'),
        ('FREQUENTLY_BOUGHT', 'Frequently Bought Together'),
        ('TRENDING', 'Trending Products'),
        ('NEW_ARRIVALS', 'New Arrivals'),
        ('SEASONAL', 'Seasonal Recommendations'),
        ('PRICE_DROP', 'Price Drop Alerts'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendations')
    product_id = models.PositiveIntegerField(db_index=True)
    recommendation_type = models.CharField(max_length=30, choices=RECOMMENDATION_TYPE_CHOICES)
    
    # Recommendation details
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, help_text="Confidence score 0-1")
    relevance_score = models.DecimalField(max_digits=5, decimal_places=4, help_text="Relevance score 0-1")
    
    # Context
    source_product_id = models.PositiveIntegerField(null=True, blank=True, help_text="Product that triggered this recommendation")
    recommendation_engine = models.ForeignKey(RecommendationEngine, on_delete=models.SET_NULL, null=True)
    
    # User interaction
    is_viewed = models.BooleanField(default=False)
    is_clicked = models.BooleanField(default=False)
    is_purchased = models.BooleanField(default=False)
    
    # Timing
    recommended_at = models.DateTimeField(auto_now_add=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    purchased_at = models.DateTimeField(null=True, blank=True)
    
    # Expiry
    expires_at = models.DateTimeField(help_text="When this recommendation expires")
    
    class Meta:
        ordering = ['-recommended_at']
        indexes = [
            models.Index(fields=['user', '-recommended_at']),
            models.Index(fields=['product_id', 'recommendation_type']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Recommend Product {self.product_id} to {self.user.username} ({self.get_recommendation_type_display()})"


class DynamicPricingRule(models.Model):
    """Dynamic pricing algorithm rules"""
    PRICING_STRATEGY_CHOICES = [
        ('DEMAND_BASED', 'Demand-Based Pricing'),
        ('COMPETITOR_BASED', 'Competitor-Based Pricing'),
        ('INVENTORY_BASED', 'Inventory-Based Pricing'),
        ('TIME_BASED', 'Time-Based Pricing'),
        ('CUSTOMER_SEGMENT', 'Customer Segment Pricing'),
        ('SEASONAL', 'Seasonal Pricing'),
        ('BUNDLE_OPTIMIZATION', 'Bundle Optimization'),
    ]
    
    name = models.CharField(max_length=100)
    strategy = models.CharField(max_length=30, choices=PRICING_STRATEGY_CHOICES)
    description = models.TextField(blank=True)
    
    # Rule conditions
    conditions = models.JSONField(default=dict, help_text="Pricing rule conditions")
    
    # Price adjustment
    min_price_change_percent = models.DecimalField(max_digits=5, decimal_places=2, default=-50)
    max_price_change_percent = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    
    # Product scope
    applicable_products = models.JSONField(default=list, help_text="List of product IDs")
    applicable_categories = models.JSONField(default=list, help_text="List of category names")
    
    # Time constraints
    active_hours_start = models.TimeField(null=True, blank=True)
    active_hours_end = models.TimeField(null=True, blank=True)
    active_days = models.JSONField(default=list, help_text="List of active days (0=Monday)")
    
    # Performance tracking
    total_applications = models.PositiveIntegerField(default=0)
    revenue_impact = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Settings
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=1, help_text="Rule priority (1=highest)")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['priority', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_strategy_display()})"


class PriceOptimization(models.Model):
    """Price optimization results and history"""
    product_id = models.PositiveIntegerField(db_index=True)
    pricing_rule = models.ForeignKey(DynamicPricingRule, on_delete=models.CASCADE, related_name='optimizations')
    
    # Original pricing
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Optimized pricing
    optimized_price = models.DecimalField(max_digits=10, decimal_places=2)
    price_change_percent = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Factors considered
    demand_factor = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    competition_factor = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    inventory_factor = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    seasonal_factor = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    
    # Implementation
    is_applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)
    reverted_at = models.DateTimeField(null=True, blank=True)
    
    # Performance tracking
    sales_before = models.PositiveIntegerField(default=0)
    sales_after = models.PositiveIntegerField(default=0)
    revenue_before = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    revenue_after = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product_id', '-created_at']),
            models.Index(fields=['pricing_rule', 'is_applied']),
        ]
    
    def revenue_impact(self):
        return self.revenue_after - self.revenue_before
    
    def __str__(self):
        return f"Product {self.product_id} - {self.original_price} → {self.optimized_price}"


class DemandForecast(models.Model):
    """Demand forecasting predictions"""
    FORECAST_TYPE_CHOICES = [
        ('DAILY', 'Daily Forecast'),
        ('WEEKLY', 'Weekly Forecast'),
        ('MONTHLY', 'Monthly Forecast'),
        ('SEASONAL', 'Seasonal Forecast'),
        ('EVENT_BASED', 'Event-Based Forecast'),
    ]
    
    product_id = models.PositiveIntegerField(db_index=True)
    forecast_type = models.CharField(max_length=20, choices=FORECAST_TYPE_CHOICES)
    
    # Forecast period
    forecast_date = models.DateField()
    forecast_period_days = models.PositiveIntegerField(default=1)
    
    # Predictions
    predicted_demand = models.PositiveIntegerField()
    confidence_interval_lower = models.PositiveIntegerField()
    confidence_interval_upper = models.PositiveIntegerField()
    confidence_level = models.DecimalField(max_digits=5, decimal_places=2, default=95.0)
    
    # Actual vs predicted
    actual_demand = models.PositiveIntegerField(null=True, blank=True)
    forecast_error = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Factors
    seasonal_component = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    trend_component = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    promotional_impact = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    external_factors = models.JSONField(default=dict, help_text="External factors considered")
    
    # Model information
    model_name = models.CharField(max_length=100)
    model_version = models.CharField(max_length=20)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-forecast_date']
        unique_together = ['product_id', 'forecast_type', 'forecast_date']
        indexes = [
            models.Index(fields=['product_id', 'forecast_date']),
            models.Index(fields=['forecast_type', 'forecast_date']),
        ]
    
    def accuracy_percentage(self):
        if self.actual_demand is not None and self.predicted_demand > 0:
            error = abs(self.actual_demand - self.predicted_demand)
            return max(0, 100 - (error / self.predicted_demand * 100))
        return None
    
    def __str__(self):
        return f"Product {self.product_id} - {self.forecast_date} ({self.predicted_demand} units)"


class FraudDetectionRule(models.Model):
    """Fraud detection rules and algorithms"""
    RULE_TYPE_CHOICES = [
        ('VELOCITY_CHECK', 'Velocity Check'),
        ('GEOLOCATION', 'Geolocation Analysis'),
        ('DEVICE_FINGERPRINT', 'Device Fingerprinting'),
        ('BEHAVIORAL_ANALYSIS', 'Behavioral Analysis'),
        ('PAYMENT_PATTERN', 'Payment Pattern Analysis'),
        ('EMAIL_DOMAIN', 'Email Domain Check'),
        ('PHONE_VERIFICATION', 'Phone Verification'),
        ('ML_SCORING', 'Machine Learning Scoring'),
    ]
    
    name = models.CharField(max_length=100)
    rule_type = models.CharField(max_length=30, choices=RULE_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Rule configuration
    rule_conditions = models.JSONField(default=dict, help_text="Rule conditions and thresholds")
    risk_score_weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    
    # Thresholds
    low_risk_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=30.0)
    medium_risk_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=60.0)
    high_risk_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=80.0)
    
    # Actions
    auto_approve_below = models.DecimalField(max_digits=5, decimal_places=2, default=20.0)
    auto_reject_above = models.DecimalField(max_digits=5, decimal_places=2, default=90.0)
    require_manual_review = models.BooleanField(default=True)
    
    # Performance metrics
    true_positives = models.PositiveIntegerField(default=0)
    false_positives = models.PositiveIntegerField(default=0)
    true_negatives = models.PositiveIntegerField(default=0)
    false_negatives = models.PositiveIntegerField(default=0)
    
    # Settings
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=1)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['priority', 'name']
    
    def precision(self):
        if (self.true_positives + self.false_positives) > 0:
            return self.true_positives / (self.true_positives + self.false_positives)
        return 0
    
    def recall(self):
        if (self.true_positives + self.false_negatives) > 0:
            return self.true_positives / (self.true_positives + self.false_negatives)
        return 0
    
    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"


class FraudAnalysis(models.Model):
    """Fraud analysis results for orders"""
    RISK_LEVEL_CHOICES = [
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
        ('CRITICAL', 'Critical Risk'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('UNDER_REVIEW', 'Under Manual Review'),
    ]
    
    order_id = models.PositiveIntegerField(unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fraud_analyses')
    
    # Risk assessment
    overall_risk_score = models.DecimalField(max_digits=5, decimal_places=2)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Individual rule scores
    rule_scores = models.JSONField(default=dict, help_text="Individual rule scores")
    
    # Risk factors
    risk_factors = models.JSONField(default=list, help_text="List of identified risk factors")
    
    # Order context
    order_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    shipping_address = models.JSONField(default=dict)
    billing_address = models.JSONField(default=dict)
    
    # Device and session
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_fingerprint = models.CharField(max_length=100, blank=True)
    
    # Geolocation
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Review information
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_fraud_cases')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['risk_level', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"Order {self.order_id} - {self.get_risk_level_display()} ({self.overall_risk_score})"


class ChatbotConfiguration(models.Model):
    """Chatbot configuration and settings"""
    CHATBOT_TYPE_CHOICES = [
        ('RULE_BASED', 'Rule-Based Chatbot'),
        ('NLP_BASED', 'NLP-Based Chatbot'),
        ('AI_POWERED', 'AI-Powered Chatbot'),
        ('HYBRID', 'Hybrid Chatbot'),
    ]
    
    name = models.CharField(max_length=100)
    chatbot_type = models.CharField(max_length=20, choices=CHATBOT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Configuration
    welcome_message = models.TextField(default="Hello! How can I help you today?")
    fallback_message = models.TextField(default="I'm sorry, I didn't understand that. Can you please rephrase?")
    
    # AI/NLP settings
    ai_model_name = models.CharField(max_length=100, blank=True)
    confidence_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=0.7)
    
    # Knowledge base
    knowledge_base = models.JSONField(default=dict, help_text="Chatbot knowledge base")
    
    # Behavior settings
    max_conversation_length = models.PositiveIntegerField(default=50)
    escalate_to_human_threshold = models.PositiveIntegerField(default=3, help_text="Failed attempts before human escalation")
    
    # Performance metrics
    total_conversations = models.PositiveIntegerField(default=0)
    successful_resolutions = models.PositiveIntegerField(default=0)
    escalations_to_human = models.PositiveIntegerField(default=0)
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_learning_enabled = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def resolution_rate(self):
        if self.total_conversations > 0:
            return (self.successful_resolutions / self.total_conversations) * 100
        return 0
    
    def __str__(self):
        return f"{self.name} ({self.get_chatbot_type_display()})"


class ChatbotConversation(models.Model):
    """Chatbot conversation logs"""
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('RESOLVED', 'Resolved'),
        ('ESCALATED', 'Escalated to Human'),
        ('ABANDONED', 'Abandoned'),
    ]
    
    conversation_id = models.CharField(max_length=50, unique=True)
    chatbot = models.ForeignKey(ChatbotConfiguration, on_delete=models.CASCADE, related_name='conversations')
    
    # User information
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField()
    
    # Conversation details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    message_count = models.PositiveIntegerField(default=0)
    
    # Resolution
    was_resolved = models.BooleanField(default=False)
    resolution_category = models.CharField(max_length=100, blank=True)
    customer_satisfaction = models.PositiveIntegerField(null=True, blank=True, help_text="1-5 rating")
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['chatbot', '-started_at']),
            models.Index(fields=['status', '-started_at']),
        ]
    
    def duration_minutes(self):
        end_time = self.ended_at or timezone.now()
        return (end_time - self.started_at).total_seconds() / 60
    
    def __str__(self):
        return f"Conversation {self.conversation_id} - {self.status}"


class ImageSearchIndex(models.Model):
    """Image-based product search index"""
    product_id = models.PositiveIntegerField(db_index=True)
    image_path = models.CharField(max_length=500)
    
    # Image features (extracted by AI)
    feature_vector = models.JSONField(default=list, help_text="Image feature vector for similarity search")
    dominant_colors = models.JSONField(default=list, help_text="Dominant colors in the image")
    
    # Image metadata
    image_width = models.PositiveIntegerField()
    image_height = models.PositiveIntegerField()
    file_size_kb = models.PositiveIntegerField()
    
    # AI analysis results
    detected_objects = models.JSONField(default=list, help_text="Objects detected in the image")
    style_tags = models.JSONField(default=list, help_text="Style tags identified")
    color_palette = models.JSONField(default=list, help_text="Color palette analysis")
    
    # Search performance
    search_count = models.PositiveIntegerField(default=0)
    match_count = models.PositiveIntegerField(default=0)
    
    # Processing status
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product_id']),
            models.Index(fields=['is_processed']),
        ]
    
    def __str__(self):
        return f"Image Index for Product {self.product_id}"


class ImageSearchQuery(models.Model):
    """Image search queries and results"""
    query_id = models.CharField(max_length=50, unique=True)
    
    # Query image
    query_image_path = models.CharField(max_length=500)
    query_image_url = models.URLField(blank=True)
    
    # User context
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField()
    
    # Search results
    results_count = models.PositiveIntegerField(default=0)
    search_results = models.JSONField(default=list, help_text="List of matching products with similarity scores")
    
    # Performance
    search_time_ms = models.PositiveIntegerField(default=0)
    
    # User interaction
    clicked_results = models.JSONField(default=list, help_text="Products clicked by user")
    purchased_products = models.JSONField(default=list, help_text="Products purchased from search results")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
    
    def click_through_rate(self):
        if self.results_count > 0:
            return (len(self.clicked_results) / self.results_count) * 100
        return 0
    
    def __str__(self):
        return f"Image Search {self.query_id} - {self.results_count} results"