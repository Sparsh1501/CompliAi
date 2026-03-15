"""
Confluence Integration Service for CompliAI (Task #22)

Integrates with Atlassian Confluence for:
- Publishing approved policies to Confluence spaces
- Syncing policy library between CompliAI and Confluence
- Importing existing policies from Confluence
"""

import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ConfluenceIntegrationService:
    """Manages Confluence API integration for policy library sync."""

    def __init__(self, db=None):
        self.db = db
        self.base_url = os.environ.get("CONFLUENCE_BASE_URL", "")
        self.api_token = os.environ.get("CONFLUENCE_API_TOKEN", "")
        self.username = os.environ.get("CONFLUENCE_USERNAME", "")
        self.space_key = os.environ.get("CONFLUENCE_SPACE_KEY", "COMPLIANCE")

    def is_configured(self) -> bool:
        """Check if Confluence integration is configured."""
        return bool(self.base_url and self.api_token and self.username)

    async def get_config_status(self) -> Dict[str, Any]:
        """Get current Confluence integration configuration status."""
        return {
            "configured": self.is_configured(),
            "base_url": self.base_url if self.base_url else None,
            "username": self.username if self.username else None,
            "space_key": self.space_key,
            "has_api_token": bool(self.api_token),
        }

    async def test_connection(self) -> Dict[str, Any]:
        """Test Confluence API connection."""
        if not self.is_configured():
            return {
                "connected": False,
                "error": "Confluence not configured. Set CONFLUENCE_BASE_URL, CONFLUENCE_API_TOKEN, and CONFLUENCE_USERNAME environment variables.",
            }

        try:
            import httpx
        except ImportError:
            return {"connected": False, "error": "httpx package not installed"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/api/space/{self.space_key}",
                    auth=(self.username, self.api_token),
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "connected": True,
                        "space_name": data.get("name", ""),
                        "space_key": self.space_key,
                    }
                else:
                    return {"connected": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def publish_policy(self, draft_id: str, parent_page_id: str = None) -> Dict[str, Any]:
        """Publish an approved policy draft to Confluence."""
        if not self.is_configured():
            return {"error": "Confluence not configured"}

        draft = await self.db.policy_drafts.find_one({"id": draft_id}, {"_id": 0})
        if not draft:
            return {"error": "Draft not found"}

        if draft.get("status") not in ("approved", "published"):
            return {"error": "Only approved or published policies can be published to Confluence"}

        content = draft.get("content", {})
        title = content.get("title", draft.get("title", "Untitled Policy"))

        # Convert policy content to Confluence storage format (XHTML)
        body_html = self._policy_to_confluence_html(content)

        try:
            import httpx
        except ImportError:
            return {"error": "httpx package not installed"}

        payload = {
            "type": "page",
            "title": title,
            "space": {"key": self.space_key},
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage",
                }
            },
        }

        if parent_page_id:
            payload["ancestors"] = [{"id": parent_page_id}]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/rest/api/content",
                    json=payload,
                    auth=(self.username, self.api_token),
                    timeout=30,
                )

                if response.status_code in (200, 201):
                    data = response.json()
                    confluence_url = f"{self.base_url}{data.get('_links', {}).get('webui', '')}"

                    # Record the sync
                    await self.db.policy_drafts.update_one(
                        {"id": draft_id},
                        {"$set": {
                            "confluence_page_id": data.get("id"),
                            "confluence_url": confluence_url,
                            "published_to_confluence_at": datetime.now(timezone.utc).isoformat(),
                        }}
                    )

                    return {
                        "page_id": data.get("id"),
                        "title": data.get("title"),
                        "url": confluence_url,
                        "status": "published",
                    }
                else:
                    return {"error": f"Confluence API error: {response.status_code} - {response.text[:200]}"}
        except Exception as e:
            return {"error": f"Confluence publish failed: {str(e)}"}

    async def import_page(self, page_id: str, user_id: str, organization: str) -> Dict[str, Any]:
        """Import a Confluence page as a policy document."""
        if not self.is_configured():
            return {"error": "Confluence not configured"}

        try:
            import httpx
        except ImportError:
            return {"error": "httpx package not installed"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/api/content/{page_id}",
                    params={"expand": "body.storage,version"},
                    auth=(self.username, self.api_token),
                    timeout=15,
                )

                if response.status_code != 200:
                    return {"error": f"Failed to fetch page: {response.status_code}"}

                data = response.json()
                title = data.get("title", "Imported Policy")
                html_content = data.get("body", {}).get("storage", {}).get("value", "")

                import uuid
                draft_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()

                draft_doc = {
                    "id": draft_id,
                    "title": title,
                    "policy_type": "imported",
                    "status": "draft",
                    "content": {
                        "title": title,
                        "sections": [{"heading": "Imported Content", "content": html_content}],
                        "summary": f"Imported from Confluence page {page_id}",
                    },
                    "source": "confluence",
                    "confluence_page_id": page_id,
                    "user_id": user_id,
                    "organization": organization,
                    "created_at": now,
                    "updated_at": now,
                }
                await self.db.policy_drafts.insert_one(draft_doc)

                return {
                    "draft_id": draft_id,
                    "title": title,
                    "source": "confluence",
                    "status": "draft",
                }
        except Exception as e:
            return {"error": f"Confluence import failed: {str(e)}"}

    async def list_space_pages(self, limit: int = 25) -> Dict[str, Any]:
        """List pages in the Confluence compliance space."""
        if not self.is_configured():
            return {"error": "Confluence not configured", "pages": []}

        try:
            import httpx
        except ImportError:
            return {"error": "httpx not installed", "pages": []}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/api/content",
                    params={"spaceKey": self.space_key, "limit": limit, "expand": "version"},
                    auth=(self.username, self.api_token),
                    timeout=15,
                )

                if response.status_code != 200:
                    return {"error": f"API error: {response.status_code}", "pages": []}

                data = response.json()
                pages = [
                    {
                        "id": p.get("id"),
                        "title": p.get("title"),
                        "type": p.get("type"),
                        "version": p.get("version", {}).get("number"),
                        "url": f"{self.base_url}{p.get('_links', {}).get('webui', '')}",
                    }
                    for p in data.get("results", [])
                ]
                return {"pages": pages, "total": data.get("size", len(pages))}
        except Exception as e:
            return {"error": str(e), "pages": []}

    def _policy_to_confluence_html(self, content: Dict) -> str:
        """Convert policy content structure to Confluence XHTML storage format."""
        html = f"<h1>{content.get('title', '')}</h1>\n"

        if content.get("summary"):
            html += f"<p><em>{content['summary']}</em></p>\n"

        for section in content.get("sections", []):
            html += f"<h2>{section.get('heading', '')}</h2>\n"
            if section.get("content"):
                html += f"<p>{section['content']}</p>\n"
            for sub in section.get("sub_sections", []):
                html += f"<h3>{sub.get('heading', '')}</h3>\n"
                if sub.get("content"):
                    html += f"<p>{sub['content']}</p>\n"

        refs = content.get("regulatory_references", [])
        if refs:
            html += "<h2>Regulatory References</h2>\n<ul>\n"
            for ref in refs:
                html += f"  <li>{ref}</li>\n"
            html += "</ul>\n"

        return html
