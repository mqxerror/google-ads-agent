---
date: 2026-04-18
type: fix
title: Don't crash the UI when Google Ads quota is exhausted
tags: [reliability, agent-quality]
---

When Google Ads API rate-limited the account (429s), the dashboard would hang on a blank screen instead of showing the cached campaign list.

Now there's a circuit breaker: if the API recently failed, the next request returns the most recent cached data immediately and the UI loads as usual. A subtle "served from cache" note appears so you know it's not live.

Workaround for stubborn quota issues: launch the backend with `SYNC_ENABLED=False` to skip the on-startup sync.
