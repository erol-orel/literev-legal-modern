from __future__ import annotations

import datetime

from typing import Any, cast

from django import forms
from django.core.exceptions import ValidationError

from literev.libs.parsing import process_search_query


class SearchForm(forms.Form):
    project_name = forms.CharField(
        max_length=256,
        widget=forms.TextInput(
            attrs={
                "class": "fs-5 form-control",
                "placeholder": "Project Name",
            }
        ),
        label="",
        required=False,
    )

    # creation date is automatically given when the Research Object is created
    # and corresponds to the current date
    query = forms.CharField(
        max_length=4096,  # 2**12
        widget=forms.TextInput(
            attrs={
                "class": "fs-5 form-control ",
                "placeholder": "New query",
            }
        ),
        label="",
        required=False,
    )

    range_begin_date = forms.DateField(
        input_formats=["%Y/%m/%d", "%Y-%m-%d"],
        widget=forms.TextInput(
            attrs={"class": "form-control", "value": "2000-01-01"}
        ),
        label="",
    )

    today = datetime.date.today().strftime("%Y-%m-%d")

    range_end_date = forms.DateField(
        input_formats=["%Y/%m/%d", "%Y-%m-%d"],
        widget=forms.TextInput(
            attrs={"class": "form-control", "value": f"{today}"}
        ),
        label="",
    )

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}

        if not data:
            raise ValidationError("Form is empty.")

        if not data.get("range_begin_date"):
            self.add_error(
                "range_begin_date",
                "Please provide the beginning date in the format YYYY-MM-DD.",
            )

        if not data.get("range_end_date"):
            self.add_error(
                "range_end_date",
                "Please provide the ending date in the format YYYY-MM-DD.",
            )

        date_begin = data.get("range_begin_date")
        date_end = data.get("range_end_date")

        if not (date_begin and date_end) or date_end < date_begin:
            self.add_error(
                "range_begin_date",
                "Please provide an ending date equal to or more recent than the beginning date.",
            )

        return data

    def clean_query(self) -> str:
        data = super().clean() or {}
        if not data:
            raise ValidationError("Form data is empty.")

        query = data.get("query", "")

        if not query:
            return ""

        # The search query field is allowed to be empty as long
        #  as a file is uploaded.
        # If a source database is selected, it will be required to have a query
        # This is validated in the UI_front views code

        (
            validated_search,
            (
                is_valid_query,
                error_in_query,
            ),
        ) = process_search_query(query)
        if not is_valid_query:
            raise ValidationError(str(error_in_query))

        # Replace "+" with spaces to show the query properly in the screen.
        return validated_search.replace("+", " ").strip()


class HistoricalForm(forms.Form):
    search = forms.CharField(
        max_length=4096,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Historical search keywords",
            }
        ),
        label="",
        required=False,
        empty_value="",
    )

    def clean_search(self) -> str:
        data = super().clean() or {}

        if not data:
            raise ValidationError("Form data is empty.")

        search = data.get("search", "")

        # TODO: Check if this will be neccesary
        # historical search do not need to check
        # for boolean operators and forbidden characters
        # check, error = error_parsing_historical(search)
        # if not check:
        #     raise ValidationError(error)

        return cast(str, search)
