from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

PLAN_LIMITS = {
    "gratis": 2,
    "starter": 999999,
    "pro": 999999,
}

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100))
    company = db.Column(db.String(100))
    plan = db.Column(db.String(20), default="gratis")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    fb_page_id = db.Column(db.String(100))
    fb_page_token = db.Column(db.Text)
    fb_page_name = db.Column(db.String(200))
    ig_account_id = db.Column(db.String(100))
    ig_account_name = db.Column(db.String(200))
    google_review_url = db.Column(db.String(500))
    trustpilot_url = db.Column(db.String(500))
    default_platform = db.Column(db.String(20), default="facebook")
    default_tone = db.Column(db.String(20), default="professionel")
    posts = db.relationship("Post", backref="user", lazy=True, order_by="Post.created_at.desc()")

    def posts_this_month(self):
        now = datetime.utcnow()
        return Post.query.filter(
            Post.user_id == self.id,
            db.extract("month", Post.created_at) == now.month,
            db.extract("year", Post.created_at) == now.year,
        ).count()

    def can_generate(self):
        limit = PLAN_LIMITS.get(self.plan, 2)
        return self.posts_this_month() < limit

    def posts_remaining(self):
        limit = PLAN_LIMITS.get(self.plan, 2)
        if limit >= 999999:
            return "∞"
        return max(0, limit - self.posts_this_month())


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    description = db.Column(db.String(300))
    platform = db.Column(db.String(20))
    tone = db.Column(db.String(20))
    post_text = db.Column(db.Text)
    hashtags = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    scheduled_at = db.Column(db.DateTime, nullable=True)
    is_published = db.Column(db.Boolean, default=True)
    image_filename = db.Column(db.String(200))
    posted_fb = db.Column(db.Boolean, default=False)
    posted_ig = db.Column(db.Boolean, default=False)


class SmsLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    customer_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="sent")
