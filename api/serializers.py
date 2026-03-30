"""
Serializers for Aremko API v1
"""

from rest_framework import serializers


class TimeSlotSerializer(serializers.Serializer):
    """Serializer for available time slots"""
    time = serializers.CharField()
    available = serializers.BooleanField(default=True)


class TubSlotSerializer(serializers.Serializer):
    """Serializer for hot tub availability"""
    tub_name = serializers.CharField()
    tub_id = serializers.IntegerField()
    slots = serializers.ListField(child=serializers.CharField())
    price_per_person = serializers.IntegerField()
    duration_minutes = serializers.IntegerField()


class MassageSlotSerializer(serializers.Serializer):
    """Serializer for massage availability"""
    type = serializers.CharField()
    type_id = serializers.IntegerField(required=False)
    slots = serializers.ListField(child=serializers.CharField())
    price = serializers.IntegerField()
    duration_minutes = serializers.IntegerField()


class CabinAddonSerializer(serializers.Serializer):
    """Serializer for cabin add-ons"""
    name = serializers.CharField()
    price = serializers.IntegerField()


class CabinAvailabilitySerializer(serializers.Serializer):
    """Serializer for cabin availability"""
    cabin_id = serializers.IntegerField()
    cabin_name = serializers.CharField()
    max_persons = serializers.IntegerField()
    price_per_night = serializers.IntegerField()
    nights = serializers.IntegerField()
    total_price = serializers.IntegerField()
    addons_available = CabinAddonSerializer(many=True)


class ServiceSummarySerializer(serializers.Serializer):
    """Serializer for service availability summary"""
    available = serializers.BooleanField()
    slots_count = serializers.IntegerField(required=False)
    cabins_count = serializers.IntegerField(required=False)


class TubAvailabilityResponseSerializer(serializers.Serializer):
    """Response serializer for tub availability"""
    date = serializers.DateField()
    service = serializers.CharField()
    available_slots = TubSlotSerializer(many=True)


class MassageAvailabilityResponseSerializer(serializers.Serializer):
    """Response serializer for massage availability"""
    date = serializers.DateField()
    service = serializers.CharField()
    available_slots = MassageSlotSerializer(many=True)


class CabinAvailabilityResponseSerializer(serializers.Serializer):
    """Response serializer for cabin availability"""
    checkin = serializers.DateField()
    checkout = serializers.DateField()
    service = serializers.CharField()
    available_cabins = CabinAvailabilitySerializer(many=True)


class AvailabilitySummaryResponseSerializer(serializers.Serializer):
    """Response serializer for availability summary"""
    date = serializers.DateField()
    summary = serializers.DictField(
        child=ServiceSummarySerializer()
    )