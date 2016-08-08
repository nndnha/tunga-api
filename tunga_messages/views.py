from django.db.models.aggregates import Max
from django.db.models.expressions import Case, When, F
from django.db.models.fields import DateTimeField
from dry_rest_permissions.generics import DRYObjectPermissions
from rest_framework import viewsets, status
from rest_framework.decorators import detail_route, list_route
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tunga_activity.filters import ActionFilter
from tunga_activity.serializers import SimpleActivitySerializer
from tunga_messages.filterbackends import MessageFilterBackend, ChannelFilterBackend
from tunga_messages.filters import MessageFilter, ChannelFilter
from tunga_messages.models import Message, Channel, ChannelUser
from tunga_messages.serializers import MessageSerializer, ChannelSerializer, DirectChannelSerializer, \
    ChannelLastReadSerializer
from tunga_messages.tasks import get_or_create_direct_channel
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS
from tunga_utils.mixins import SaveUploadsMixin
from tunga_utils.pagination import LargeResultsSetPagination


class ChannelViewSet(viewsets.ModelViewSet, SaveUploadsMixin):
    """
    Channel Resource
    """
    queryset = Channel.objects.all().annotate(
        latest_message_created_at=Max('messages__created_at')
    ).annotate(latest_activity_at=Case(
        When(
            latest_message_created_at__isnull=True,
            then='created_at'
        ),
        When(
            latest_message_created_at__gt=F('created_at'),
            then='latest_message_created_at'
        ),
        default='created_at',
        output_field=DateTimeField()
    )).order_by('-latest_activity_at')
    serializer_class = ChannelSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = ChannelFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ChannelFilterBackend,)
    pagination_class = LargeResultsSetPagination
    search_fields = (
        'subject', 'channeluser__user__username', 'channeluser__user__first_name',
        'channeluser__user__last_name'
    )

    @list_route(
        methods=['post'], url_path='direct',
        permission_classes=[IsAuthenticated], serializer_class=DirectChannelSerializer
    )
    def direct_channel(self, request):
        """
        Gets or creates a direct channel to the user
        ---
        request_serializer: DirectChannelSerializer
        response_serializer: ChannelSerializer
        """
        serializer = self.get_serializer(data=request.data)
        channel = None
        if serializer.is_valid(raise_exception=True):
            user = serializer.validated_data['user']
            channel = get_or_create_direct_channel(request.user, user)
        if not channel:
            return Response(
                {'status': "Couldn't get or create a direct channel"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        response_serializer = ChannelSerializer(channel)
        return Response(response_serializer.data)

    @detail_route(
        methods=['post'], url_path='read',
        permission_classes=[IsAuthenticated], serializer_class=ChannelLastReadSerializer
    )
    def update_read(self, request, pk=None):
        """
        Updates user's read_at for channel
        ---
        request_serializer: ChannelLastReadSerializer
        response_serializer: ChannelSerializer
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        last_read = serializer.validated_data['last_read']
        channel = get_object_or_404(self.get_queryset(), pk=pk)
        if channel.has_object_read_permission(request):
            ChannelUser.objects.update_or_create(user=request.user, channel=channel, defaults={'last_read': last_read})
            response_serializer = ChannelSerializer(channel, context={'request': request})
            return Response(response_serializer.data)
        return Response(
                {'status': 'Unauthorized', 'message': 'No access to this channel'},
                status=status.HTTP_401_UNAUTHORIZED
            )

    @detail_route(
        methods=['get'], url_path='activity',
        permission_classes=[IsAuthenticated],
        serializer_class=SimpleActivitySerializer,
        filter_class=None,
        filter_backends=DEFAULT_FILTER_BACKENDS,
        search_fields=('messages__body', 'uploads__file', 'messages__attachments__file')
    )
    def activity(self, request, pk=None):
        """
        Channel Activity Endpoint
        ---
        response_serializer: SimpleActivitySerializer
        #omit_parameters:
        #    - query
        """
        channel = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(request, channel)

        queryset = ActionFilter(request.GET, self.filter_queryset(channel.target_actions.all().order_by('-id')))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MessageViewSet(viewsets.ModelViewSet, SaveUploadsMixin):
    """
    Message Resource
    """
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = MessageFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (MessageFilterBackend,)
    search_fields = ('user__username', 'body',)

    @detail_route(
        methods=['post'], url_path='read',
        permission_classes=[IsAuthenticated]
    )
    def update_read(self, request, pk=None):
        """
        Set message as last_read in it's channel
        ---
        response_serializer: ChannelSerializer
        """
        message = get_object_or_404(self.get_queryset(), pk=pk)

        if message.has_object_read_permission(request):
            ChannelUser.objects.update_or_create(
                user=request.user, channel=message.channel, defaults={'last_read': message.id}
            )
            response_serializer = ChannelSerializer(message.channel)
            return Response(response_serializer.data)
        return Response(
                {'status': 'Unauthorized', 'message': 'No access to this message'},
                status=status.HTTP_401_UNAUTHORIZED
            )

