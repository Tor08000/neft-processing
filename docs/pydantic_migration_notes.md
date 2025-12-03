# Pydantic v2 migration notes

This release starts a gradual migration of schema definitions to the Pydantic v2 style. Admin API schemas now rely on `ConfigDict(from_attributes=True)` instead of class-based `Config.orm_mode` and use `field_validator` for model validation. The change removes the v1 deprecation warnings seen in the admin tests and prepares the project for future FastAPI/Pydantic upgrades.
