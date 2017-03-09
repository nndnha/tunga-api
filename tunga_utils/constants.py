# User Types
USER_TYPE_DEVELOPER = 1
USER_TYPE_PROJECT_OWNER = 2
USER_TYPE_PROJECT_MANAGER = 3

# User Source
USER_SOURCE_DEFAULT = 1
USER_SOURCE_TASK_WIZARD = 2

# Source
TASK_SOURCE_DEFAULT = 1
TASK_SOURCE_NEW_USER = 2

# Currencies
CURRENCY_BTC = 'BTC'
CURRENCY_EUR = 'EUR'
CURRENCY_USD = 'USD'
CURRENCY_UGX = 'UGX'
CURRENCY_TZS = 'TZS'
CURRENCY_NGN = 'NGN'

# BTC Wallets
BTC_WALLET_PROVIDER_COINBASE = 'coinbase'

# App Integrations
APP_INTEGRATION_PROVIDER_GITHUB = 'github'
APP_INTEGRATION_PROVIDER_SLACK = 'slack'
APP_INTEGRATION_PROVIDER_HARVEST = 'harvest'

# Developer Payment Methods
PAYMENT_METHOD_BTC_WALLET = 'btc_wallet'
PAYMENT_METHOD_BTC_ADDRESS = 'btc_address'
PAYMENT_METHOD_MOBILE_MONEY = 'mobile_money'

# Task Types
TASK_TYPE_WEB = 1
TASK_TYPE_MOBILE = 2
TASK_TYPE_OTHER = 3

# Task scope
TASK_SCOPE_TASK = 1
TASK_SCOPE_ONGOING = 2
TASK_SCOPE_PROJECT = 3

# Task Coders
TASK_CODERS_NEEDED_ONE = 1
TASK_CODERS_NEEDED_MULTIPLE = -1

# Billing Type
TASK_BILLING_METHOD_FIXED = 1
TASK_BILLING_METHOD_HOURLY = 2

# Task Payment Methods
TASK_PAYMENT_METHOD_BITONIC = 'bitonic'
TASK_PAYMENT_METHOD_BITCOIN = 'bitcoin'
TASK_PAYMENT_METHOD_BANK = 'bank'

# Transaction and Action Statuses
STATUS_INITIAL = 'initial'
STATUS_PENDING = 'pending'
STATUS_INITIATED = 'initiated'
STATUS_SUBMITTED = 'submitted'
STATUS_PROCESSING = 'processing'
STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'
STATUS_ACCEPTED = 'accepted'
STATUS_REJECTED = 'rejected'
STATUS_APPROVED = 'approved'
STATUS_DECLINED = 'declined'

# Request Statuses
REQUEST_STATUS_INITIAL = 0
REQUEST_STATUS_ACCEPTED = 1
REQUEST_STATUS_REJECTED = 2

# Channel Types
CHANNEL_TYPE_DIRECT = 1
CHANNEL_TYPE_TOPIC = 2
CHANNEL_TYPE_SUPPORT = 3
CHANNEL_TYPE_DEVELOPER = 4

# Task Visibility
VISIBILITY_DEVELOPER = 1
VISIBILITY_MY_TEAM = 2
VISIBILITY_CUSTOM = 3
VISIBILITY_ONLY_ME = 4

# Support Visibility
VISIBILITY_ALL = 'all'
VISIBILITY_DEVELOPERS = 'developers'
VISIBILITY_PROJECT_OWNERS = 'project-owners'

# Update Schedule Periods
UPDATE_SCHEDULE_HOURLY = 1
UPDATE_SCHEDULE_DAILY = 2
UPDATE_SCHEDULE_WEEKLY = 3
UPDATE_SCHEDULE_MONTHLY = 4
UPDATE_SCHEDULE_QUATERLY = 5
UPDATE_SCHEDULE_ANNUALLY = 6

# Progress Event Types
PROGRESS_EVENT_TYPE_DEFAULT = 1
PROGRESS_EVENT_TYPE_PERIODIC = 2
PROGRESS_EVENT_TYPE_MILESTONE = 3
PROGRESS_EVENT_TYPE_SUBMIT = 4
PROGRESS_EVENT_TYPE_COMPLETE = 5

# Progress Report Status
PROGRESS_REPORT_STATUS_ON_SCHEDULE = 1
PROGRESS_REPORT_STATUS_BEHIND = 2
PROGRESS_REPORT_STATUS_STUCK = 3

# Integration Types
INTEGRATION_TYPE_REPO = 1
INTEGRATION_TYPE_ISSUE = 2

# Rating Criteria
RATING_CRITERIA_CODING = 1
RATING_CRITERIA_COMMUNICATION = 2
RATING_CRITERIA_SPEED = 3

# Months
MONTHS = (
    (1, 'Jan'),
    (2, 'Feb'),
    (3, 'Mar'),
    (4, 'Apr'),
    (5, 'May'),
    (6, 'Jun'),
    (7, 'Jul'),
    (8, 'Aug'),
    (9, 'Sep'),
    (10, 'Oct'),
    (11, 'Nov'),
    (12, 'Dec')
)

# Country Codes
COUNTRY_CODE_UGANDA = '256'
COUNTRY_CODE_TANZANIA = '255'
COUNTRY_CODE_NIGERIA = '234'


# Contact request item
CONTACT_REQUEST_ITEM_DO_IT_YOURSELF = "self_guided"
CONTACT_REQUEST_ITEM_ONBOARDING = "onboarding"
CONTACT_REQUEST_ITEM_ONBOARDING_SPECIAL = "onboarding_special"
CONTACT_REQUEST_ITEM_PROJECT = "project"

SESSION_VISITOR_EMAIL = 'visitor_email'

