import re

import httpx

from lacis.collectors.endpoints import (
    BODACC_HOST,
    BODACC_RECORDS_PATH,
    COMPANY_REGISTER_HOST,
    COMPANY_SEARCH_PATH,
    MAXIMUM_COMPANIES_PER_PAGE,
    MAXIMUM_NOTICES_PER_PAGE,
)
from lacis.collectors.fictional_records import (
    FictionalCompany,
    FictionalEstablishment,
    FictionalNaturalPerson,
    FictionalNotice,
    FictionalScenario,
    JsonObject,
    searchable,
)

SIREN_LENGTH = 9
SIRET_LENGTH = 14
DEFAULT_COMPANIES_PER_PAGE = 10
DEFAULT_NOTICES_PER_PAGE = 10
REGISTER_FILTER = re.compile(r'^\s*registre\s*=\s*"(?P<siren>[0-9 ]+)"\s*$')
NOTICE_ORDERS = {"dateparution asc": False, "dateparution": False, "dateparution desc": True}


class InvalidParameterError(Exception):
    pass


def whole_number(parameters: httpx.QueryParams, name: str, default: int, minimum: int) -> int:
    text = parameters.get(name)
    if text is None:
        return default
    if not text.isdigit() or int(text) < minimum:
        raise InvalidParameterError(f"Paramètre {name} invalide : {text}")
    return int(text)


def page_count(result_count: int, per_page: int) -> int:
    return max(1, -(-result_count // per_page))


def matches_every_word(words: list[str], text: str) -> bool:
    return all(word in text for word in words)


def directed_by(company: FictionalCompany, last_name: str, first_names: str) -> bool:
    if not company.diffusible:
        return False
    return any(
        isinstance(director, FictionalNaturalPerson)
        and director.diffusible
        and searchable(last_name) in searchable(director.last_name)
        and searchable(first_names) in searchable(director.first_names)
        for director in company.directors
    )


class FakeApi:
    def __init__(self, scenario: FictionalScenario) -> None:
        self.scenario = scenario
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        route = (request.method, request.url.host, request.url.path)
        try:
            if route == ("GET", COMPANY_REGISTER_HOST, COMPANY_SEARCH_PATH):
                return httpx.Response(200, json=self.search_companies(request.url.params))
            if route == ("GET", BODACC_HOST, BODACC_RECORDS_PATH):
                return httpx.Response(200, json=self.search_notices(request.url.params))
        except InvalidParameterError as invalid_parameter:
            return self.invalid_parameter_response(request, invalid_parameter)
        return httpx.Response(404, json={"erreur": f"Ressource inconnue : {request.url.path}"})

    @staticmethod
    def invalid_parameter_response(
        request: httpx.Request, invalid_parameter: InvalidParameterError
    ) -> httpx.Response:
        if request.url.host == BODACC_HOST:
            return httpx.Response(
                400,
                json={
                    "error_code": "InvalidRESTParameterError",
                    "message": str(invalid_parameter),
                },
            )
        return httpx.Response(400, json={"erreur": str(invalid_parameter)})

    def search_companies(self, parameters: httpx.QueryParams) -> JsonObject:
        page = whole_number(parameters, "page", 1, 1)
        per_page = whole_number(parameters, "per_page", DEFAULT_COMPANIES_PER_PAGE, 1)
        if per_page > MAXIMUM_COMPANIES_PER_PAGE:
            raise InvalidParameterError(f"Paramètre per_page invalide : {per_page}")
        query = parameters.get("q", "").strip()
        last_name = parameters.get("nom_personne", "").strip()
        first_names = parameters.get("prenoms_personne", "").strip()
        if not query and not last_name:
            raise InvalidParameterError("Veuillez indiquer au moins un terme de recherche.")
        results: list[JsonObject] = []
        for company in self.scenario.companies:
            if last_name and not directed_by(company, last_name, first_names):
                continue
            matching_establishments = self.matching_establishments(company, query)
            if matching_establishments is not None:
                results.append(company.record(matching_establishments))
        first_result = (page - 1) * per_page
        return {
            "results": results[first_result : first_result + per_page],
            "total_results": len(results),
            "page": page,
            "per_page": per_page,
            "total_pages": page_count(len(results), per_page),
        }

    @staticmethod
    def matching_establishments(
        company: FictionalCompany, query: str
    ) -> list[FictionalEstablishment] | None:
        digits = query.replace(" ", "")
        if digits.isdigit() and len(digits) == SIREN_LENGTH:
            return list(company.establishments) if company.siren == digits else None
        if digits.isdigit() and len(digits) == SIRET_LENGTH:
            found = [
                establishment
                for establishment in company.establishments
                if establishment.siret(company.siren) == digits
            ]
            return found or None
        words = searchable(query).split()
        found = [
            establishment
            for establishment in company.establishments
            if matches_every_word(words, company.searchable_text(establishment))
        ]
        return found or None

    def search_notices(self, parameters: httpx.QueryParams) -> JsonObject:
        limit = whole_number(parameters, "limit", DEFAULT_NOTICES_PER_PAGE, 1)
        if limit > MAXIMUM_NOTICES_PER_PAGE:
            raise InvalidParameterError(f"Paramètre limit invalide : {limit}")
        offset = whole_number(parameters, "offset", 0, 0)
        notices = self.filtered_notices(parameters.get("where"))
        order = parameters.get("order_by")
        if order is not None:
            if order not in NOTICE_ORDERS:
                raise InvalidParameterError(f"Tri non pris en charge : {order}")
            notices.sort(key=lambda notice: notice.publication_date, reverse=NOTICE_ORDERS[order])
        return {
            "total_count": len(notices),
            "results": [notice.record() for notice in notices[offset : offset + limit]],
        }

    def filtered_notices(self, where: str | None) -> list[FictionalNotice]:
        if where is None:
            return list(self.scenario.notices)
        register_filter = REGISTER_FILTER.match(where)
        if register_filter is None:
            raise InvalidParameterError(f"Filtre non pris en charge : {where}")
        siren = register_filter["siren"].replace(" ", "")
        return [notice for notice in self.scenario.notices if notice.company.siren == siren]
