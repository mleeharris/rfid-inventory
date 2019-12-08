from django import forms

from .models import Item, Location


class LocationForm(forms.ModelForm):
    """
    Custom location create/edit form that sanitises names.
    """

    class Meta:
        model = Location
        fields = ["name", "description", "notes", "latitude", "longitude"]

    def clean_name(self):
        if "|" in self.cleaned_data["name"]:
            raise forms.ValidationError(
                "The | character is forbidden in location names"
            )
        return self.normalise_name(self.cleaned_data["name"])

    @classmethod
    def normalise_name(cls, name):
        return " / ".join(x.strip() for x in name.split("/") if x.strip())


class ReparentForm(forms.Form):
    """
    Allows reparenting of locations.
    """

    name = forms.CharField(help_text="Prefix or location name to reparent")
    new_name = forms.CharField(
        help_text="New location prefix, or / to make its children top-level"
    )

    def clean_name(self):
        name = LocationForm.normalise_name(self.cleaned_data["name"])
        matches = Location.objects.filter(name__startswith=name)
        if not matches.exists():
            raise forms.ValidationError("No locations match this prefix")
        return name

    def clean_new_name(self):
        new_name = LocationForm.normalise_name(self.cleaned_data["new_name"])
        if self.cleaned_data.get("name") and new_name.startswith(
            self.cleaned_data["name"]
        ):
            raise forms.ValidationError("Cannot move locations under themselves")
        return new_name


class BaseItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ["name", "description", "location", "serial", "notes"]
        widgets = {"description": forms.TextInput(), "serial": forms.TextInput()}


class EditItemForm(BaseItemForm):

    tags = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        # Grab the tags off of the Tag model
        if kwargs.get("instance"):
            initial = kwargs.setdefault("initial", {})
            initial["tags"] = "\n".join(
                t.id for t in kwargs["instance"].tags.order_by("id")
            )
        super().__init__(*args, **kwargs)

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        # Re-hydrate tags into model objects
        saved_tags = set(
            line.strip()
            for line in self.cleaned_data.get("tags", "").split("\n")
            if line.strip()
        )
        current_tags = set(t.id for t in instance.tags.all())
        for added_tag in saved_tags.difference(current_tags):
            instance.tags.create(id=added_tag)
        for removed_tag in current_tags.difference(saved_tags):
            instance.tags.filter(id=removed_tag).delete()
        return instance


class CreateItemForm(BaseItemForm):

    tag = forms.CharField(
        required=False, help_text="Optional tag to immediately associate with"
    )

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        # If we got a tag, add that too
        if self.cleaned_data["tag"]:
            instance.tags.create(id=self.cleaned_data["tag"])
        return instance
