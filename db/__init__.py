"""Shared database utilities and engine creation live under this top-level `db` package.

The code here is *not* imported by the main application yet; it is introduced in
preparation for multi-tenant RLS support and will replace the existing
`camp44.db.session` once the async stack and auth middleware are wired.
"""
