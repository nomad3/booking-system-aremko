from django.db import models

from .enums import (
    BlockType,
    InterestType,
    PlaceType,
    ProfileType,
    DurationType,
)


class DurationCase(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    duration_type = models.CharField(max_length=30, choices=DurationType.choices)
    days = models.PositiveSmallIntegerField()
    nights = models.PositiveSmallIntegerField()
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["sort_order", "days"]
        verbose_name = "Caso de duración"
        verbose_name_plural = "Casos de duración"

    def __str__(self):
        return f"{self.code} — {self.name}"


class Circuit(models.Model):
    number = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    short_description = models.CharField(max_length=255)
    long_description = models.TextField(blank=True)
    duration_case = models.ForeignKey(
        DurationCase,
        on_delete=models.PROTECT,
        related_name="circuits",
    )
    primary_interest = models.CharField(
        max_length=30,
        choices=InterestType.choices,
        db_index=True,
    )
    recommended_profile = models.CharField(
        max_length=20,
        choices=ProfileType.choices,
        blank=True,
    )
    is_romantic = models.BooleanField(default=False)
    is_family_friendly = models.BooleanField(default=False)
    is_adventure = models.BooleanField(default=False)
    is_rain_friendly = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False)
    published = models.BooleanField(default=False, db_index=True)
    featured = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "number"]
        verbose_name = "Circuito"
        verbose_name_plural = "Circuitos"

    def __str__(self):
        return f"#{self.number} — {self.name}"


class CircuitDay(models.Model):
    circuit = models.ForeignKey(
        Circuit,
        on_delete=models.CASCADE,
        related_name="days",
    )
    day_number = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)
    block_type = models.CharField(max_length=30, choices=BlockType.choices)
    summary = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["circuit", "day_number", "sort_order"]
        verbose_name = "Día de circuito"
        verbose_name_plural = "Días de circuito"
        constraints = [
            models.UniqueConstraint(
                fields=["circuit", "day_number"],
                name="uq_circuitday_circuit_day",
            ),
        ]

    def __str__(self):
        return f"{self.circuit} · Día {self.day_number}: {self.title}"


class Place(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    place_type = models.CharField(
        max_length=30,
        choices=PlaceType.choices,
        db_index=True,
    )
    short_description = models.CharField(max_length=255)
    long_description = models.TextField(blank=True)
    location_label = models.CharField(max_length=200)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    is_rain_friendly = models.BooleanField(default=False)
    is_romantic = models.BooleanField(default=False)
    is_family_friendly = models.BooleanField(default=False)
    is_adventure_related = models.BooleanField(default=False)
    practical_tips = models.TextField(blank=True)
    safety_notes = models.TextField(blank=True)
    did_you_know = models.TextField(blank=True)
    nobody_tells_you = models.TextField(blank=True)
    published = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Lugar"
        verbose_name_plural = "Lugares"

    def __str__(self):
        return self.name


class CircuitPlace(models.Model):
    circuit_day = models.ForeignKey(
        CircuitDay,
        on_delete=models.CASCADE,
        related_name="place_stops",
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.PROTECT,
        related_name="circuit_stops",
    )
    visit_order = models.PositiveSmallIntegerField(default=0)
    is_main_stop = models.BooleanField(default=False)

    class Meta:
        ordering = ["circuit_day", "visit_order"]
        verbose_name = "Parada de circuito"
        verbose_name_plural = "Paradas de circuito"

    def __str__(self):
        return f"{self.circuit_day} · {self.place}"
