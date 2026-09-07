"""
VisionDecor SQLAlchemy ORM models.

Table -> report layer mapping (see PLAN.md / decision log D013):

  users, user_preferences, design_sessions, jobs      -> cross-cutting / Layer 1
  room_images, room_analyses, detected_objects        -> Layer 2 (Image Analysis)
  style_predictions                                   -> Layer 3 (Intelligence)
  design_principles                                   -> Layer 3 (RAG knowledge base, D006a)
  furniture_catalog, recommendations,
    recommendation_items                              -> Layer 3 (Recommendation)
  layouts, layout_objects                             -> Layer 4 (Layout Optimization)
  visualizations, feedback                            -> Layer 5 (Visualization & Data)

Every model is imported here so `Base.metadata` sees the full schema when
Alembic autogenerates a migration, and so `from backend.models import User`
etc. works from anywhere in the app.
"""

from backend.models.base import Base
from backend.models.user import User, UserPreference
from backend.models.session import DesignSession, Job
from backend.models.room import RoomImage, RoomAnalysis, DetectedObject
from backend.models.style import StylePrediction
from backend.models.principle import DesignPrinciple
from backend.models.catalog import FurnitureCatalogItem
from backend.models.recommendation import Recommendation, RecommendationItem
from backend.models.layout import Layout, LayoutObject
from backend.models.visualization import Visualization
from backend.models.feedback import Feedback

__all__ = [
    "Base",
    "User",
    "UserPreference",
    "DesignSession",
    "Job",
    "RoomImage",
    "RoomAnalysis",
    "DetectedObject",
    "StylePrediction",
    "DesignPrinciple",
    "FurnitureCatalogItem",
    "Recommendation",
    "RecommendationItem",
    "Layout",
    "LayoutObject",
    "Visualization",
    "Feedback",
]
