from django.forms import Select

class PrecioSelect(Select):
    def __init__(self, *args, **kwargs):
        self.attribute = kwargs.pop('attribute', {})
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if self.attribute and str(value) in self.attribute:
            option['attrs']['data-precio-unitario'] = str(self.attribute[str(value)])
        return option
