from __future__ import annotations

from dataclasses import dataclass

from neft_logistics_service.providers.base import BaseProvider, ProviderUnavailableError


@dataclass
class UnavailableProvider(BaseProvider):
    name: str
    owner: str

    def _raise(self) -> None:
        raise ProviderUnavailableError(
            code=f"{self.owner}_{self.name}",
            mode=self.name,
            provider=self.owner,
        )

    def preview_route(self, request):
        self._raise()

    def compute_eta(self, request):
        self._raise()

    def compute_deviation(self, request):
        self._raise()

    def explain_eta(self, request):
        self._raise()

    def explain_deviation(self, request):
        self._raise()

    def fleet_list(self, request):
        self._raise()

    def fleet_upsert(self, request):
        self._raise()

    def trip_create(self, request):
        self._raise()

    def trip_get_status(self, trip_id: str):
        self._raise()

    def fuel_get_consumption(self, request):
        self._raise()


__all__ = ["UnavailableProvider"]
