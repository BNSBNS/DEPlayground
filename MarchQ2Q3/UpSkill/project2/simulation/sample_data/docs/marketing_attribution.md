# Marketing Attribution

## Model

The marketing_attribution model uses a last-touch attribution model. Each order is attributed to the marketing channel of the customer's most recent session before the purchase.

## Channels

Channels are derived from the session UTM parameters:
- **organic**: No UTM tags, direct or search engine traffic
- **paid_search**: Google Ads, Bing Ads
- **social**: Facebook, Instagram, TikTok
- **email**: Email campaigns
- **referral**: Partner referral links
- **direct**: Direct URL entry

## Metrics

- **attributed_revenue**: Total order revenue attributed to the channel
- **attributed_orders**: Count of orders attributed to the channel
- **CPA (Cost Per Acquisition)**: Marketing spend divided by attributed orders

## Limitations

Last-touch attribution overweights bottom-of-funnel channels (paid search, email) and underweights awareness channels (social, display). A multi-touch model is planned for Q3.
