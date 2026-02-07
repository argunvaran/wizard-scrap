from django import forms

class ImportDataForm(forms.Form):
    # This form will be dynamically populated in the view 
    # based on available tables in the SQLite database
    pass

class CountryFilterForm(forms.Form):
    COUNTRY_CHOICES = [
        ('ALL', 'Tüm Ülkeler'),
        ('TURKEY', 'Türkiye'),
        ('ENGLAND', 'İngiltere'),
        ('SPAIN', 'İspanya'),
        ('ITALY', 'İtalya'),
    ]
    country = forms.ChoiceField(choices=COUNTRY_CHOICES, required=False, label="Ülke Seç")
