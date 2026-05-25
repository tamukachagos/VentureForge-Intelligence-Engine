from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
import xml.etree.ElementTree as ET

import httpx


@dataclass(frozen=True)
class SourceFinding:
    source: str
    url: str
    title: str
    text: str
    collected_at: str
    cost_usd: float = 0.0
    confidence: float = 0.5


class SourceConnector(Protocol):
    name: str

    def collect(self) -> list[SourceFinding]:
        raise NotImplementedError


class PaidSourceConnector(SourceConnector, Protocol):
    estimated_cost_usd: float


class HackerNewsConnector:
    name = "hacker_news"

    def __init__(self, client_factory: Callable[..., object] = httpx.Client) -> None:
        self.client_factory = client_factory

    def collect(self) -> list[SourceFinding]:
        with self.client_factory(timeout=20) as client:
            ids = client.get("https://hacker-news.firebaseio.com/v0/topstories.json").json()[:30]
            findings: list[SourceFinding] = []
            for item_id in ids[:10]:
                item = client.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
                ).json()
                title = item.get("title", "")
                url = item.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
                findings.append(
                    SourceFinding(
                        source=self.name,
                        url=url,
                        title=title,
                        text=title,
                        collected_at=str(item.get("time", "")),
                        confidence=0.6,
                    )
                )
        return findings


class GitHubSearchConnector:
    name = "github_search"

    def __init__(
        self,
        token: str = "",
        query: str = "AI agents created:>2026-01-01",
        client_factory: Callable[..., object] = httpx.Client,
    ) -> None:
        self.token = token
        self.query = query
        self.client_factory = client_factory

    def collect(self) -> list[SourceFinding]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        params = {"q": self.query, "sort": "stars", "order": "desc", "per_page": "20"}
        with self.client_factory(timeout=30) as client:
            data = client.get(
                "https://api.github.com/search/repositories",
                headers=headers,
                params=params,
            ).json()
        findings = []
        for item in data.get("items", []):
            findings.append(
                SourceFinding(
                    source=self.name,
                    url=item["html_url"],
                    title=item["full_name"],
                    text=item.get("description") or "",
                    collected_at=item.get("updated_at", ""),
                    confidence=0.65,
                )
            )
        return findings


class RSSConnector:
    name = "rss"

    def __init__(
        self,
        feed_urls: list[str],
        client_factory: Callable[..., object] = httpx.Client,
    ) -> None:
        self.feed_urls = feed_urls
        self.client_factory = client_factory

    def collect(self) -> list[SourceFinding]:
        findings: list[SourceFinding] = []
        with self.client_factory(timeout=30) as client:
            for feed_url in self.feed_urls:
                response = client.get(feed_url)
                response.raise_for_status()
                root = ET.fromstring(response.text)
                for item in root.findall(".//item")[:20]:
                    title = item.findtext("title") or ""
                    link = item.findtext("link") or feed_url
                    description = item.findtext("description") or title
                    findings.append(
                        SourceFinding(
                            source=self.name,
                            url=link,
                            title=title,
                            text=description,
                            collected_at=item.findtext("pubDate") or "",
                            confidence=0.55,
                        )
                    )
                atom_namespace = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", atom_namespace)[:20]:
                    title = entry.findtext("atom:title", default="", namespaces=atom_namespace)
                    link = feed_url
                    link_element = entry.find("atom:link", atom_namespace)
                    if link_element is not None and link_element.get("href"):
                        link = link_element.get("href")
                    summary = entry.findtext("atom:summary", default=title, namespaces=atom_namespace)
                    updated = entry.findtext("atom:updated", default="", namespaces=atom_namespace)
                    findings.append(
                        SourceFinding(
                            source=self.name,
                            url=link,
                            title=title,
                            text=summary,
                            collected_at=updated,
                            confidence=0.55,
                        )
                    )
        return findings


class PaidSearchConnector:
    def __init__(
        self,
        name: str,
        endpoint_url: str,
        api_key: str,
        query: str,
        estimated_cost_usd: float,
        client_factory: Callable[..., object] = httpx.Client,
    ) -> None:
        self.name = name
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.query = query
        self.estimated_cost_usd = estimated_cost_usd
        self.client_factory = client_factory

    def collect(self) -> list[SourceFinding]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"query": self.query}
        with self.client_factory(timeout=30) as client:
            response = client.post(self.endpoint_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        findings: list[SourceFinding] = []
        for item in _extract_result_items(data):
            title = str(item.get("title") or item.get("name") or "Paid search result")
            url = str(item.get("url") or item.get("link") or "")
            text = str(item.get("content") or item.get("snippet") or item.get("text") or title)
            findings.append(
                SourceFinding(
                    source=self.name,
                    url=url,
                    title=title,
                    text=text,
                    collected_at="",
                    cost_usd=self.estimated_cost_usd / max(1, len(_extract_result_items(data))),
                    confidence=0.7,
                )
            )
        return findings


def _extract_result_items(data: dict) -> list[dict]:
    for key in ("results", "items", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []
