# QuizlyNotes monetisation: plan and setup

## The model: unlimited studying, metered AI

Research on competitors (Oct 2026):

| Product | Free | Paid |
|---|---|---|
| Quizlet | Caps *studying* (5-question tests, 20 Learn rounds/month), ads | Plus $35.99/yr, Plus Unlimited $44.99/yr |
| Knowt | Unlimited studying, AI on a monthly allowance | Ultra $12.49/mo yearly, $24.99 monthly |
| YouLearn | 3 uploads/day, 35 quiz questions/day | Pro $12/mo yearly, $20 monthly |
| Gizmo | 10 AI quizzes/day | ~$77 to $155/yr |

Quizlet's study caps are widely disliked by students. Knowt's approach (never limit
revision, only meter the expensive AI) wins goodwill and word of mouth, so
QuizlyNotes follows it. That also matches your goal of keeping as much as
possible free to grow the user base.

Freemium benchmarks: about 3 to 8% of free users convert, and "reverse trials"
(start everyone on the paid plan, then downgrade) convert at 8 to 12%. Freemium
also brings in about twice as many signups as a card-required trial.

### Free (forever)
- **Unlimited studying**: quizzes, flashcards, spaced repetition, Match / Speed / Write games, scores, saved sets, export
- 5 new AI study sets per month (resets on the 1st)
- 2 quiz regenerations per set
- 15 AI note edits (Simplify / Improve) per month
- PDFs up to 30 pages / 10MB, up to 15 questions per quiz
- All 10 question types
- Share quizzes with a link

### Pro: £4.99/month or £29.99/year (£2.50/mo, 50% off)
- Unlimited AI study sets (fair use: 300/month) and unlimited regenerations
- PDFs up to 150 pages / 30MB, up to 60 questions per quiz
- Unlimited Simplify / Improve
- **Mock exams**: a timed quiz mixing questions from every set in a subject (new)
- **Weak spots**: a cross-set drill of the questions you keep getting wrong (new)

The two Pro-only features cost nothing in AI fees, because they reuse existing
questions. Pricing sits under Knowt and YouLearn and near Quizlet Plus Unlimited.
The yearly plan is the default on the pricing page because it fits students'
exam cycles.

### Growth and conversion levers (built)
1. **Reverse trial**: every new account gets 7 days of Pro, with no card needed (14 days if invited). Existing users get it once as a launch gift on their next login.
2. **Moment-of-need upgrade prompts**: hitting a limit opens an upgrade dialog instead of an error. It also offers "earn free Pro weeks", so free users can still get what they need.
3. **Usage meter** in the library ("3 of 5 free AI sets left") and on the New set page, plus a trial countdown banner and a header chip.
4. **Referrals**: "give a week, get a week". The invited friend gets a 14-day trial, and the inviter gets 7 days of Pro once the friend makes their first set, so empty signups don't count. Rewards are capped at 90 days ahead.
5. **Public share links**: a "Share this quiz" link on any set that anyone can play without an account. It ends with "Make quizzes from my own notes", and friends who sign up count as the sharer's referrals. This is the main viral loop.
6. **Pricing page** at `/pricing`: indexable, with FAQ, plan comparison and a monthly/yearly toggle. The home page structured data now lists the offers.
7. **Promo codes**: hashed in the database. Create them with `flask promo` (e.g. for student societies or launch promotions). Stripe Checkout also accepts Stripe coupon codes.

## Your free access

- **Owner code (lifetime Pro, 5 uses so you can give some away):** see the chat message or the project notes. Redeem it in **Settings → Plan → Promo code** or on the pricing page.
- Optional backup: set `ADMIN_EMAILS=joefergsn@gmail.com` on Cloud Run, and that email always has Pro.

Create more codes at any time:
```bash
flask --app wsgi promo "Uni society" --days 30 --uses 100     # 30 days Pro, 100 uses
flask --app wsgi promo "Friend" --uses 1                       # lifetime Pro, 1 use
```

## On/off switch

Monetisation is **off by default** (`MONETISATION_ENABLED` unset). While it's off,
everyone gets the full product with Pro's fair-use caps, there are no trials,
and the pricing page, plan badges, upgrade prompts, invite rewards and Pro wording
are hidden (`/pricing`, `/redeem` and `/r/...` redirect home). Turn it on once
Stripe is set up:

```bash
gcloud run services update flask-app --region europe-west1 --update-env-vars MONETISATION_ENABLED=true
```

Existing users then get their 7-day trial on their next login.

## Turning on payments (about 20 minutes, you need to do this)

Until Stripe keys are set, everything works except the checkout buttons, which
show "Payments open soon". Trials, limits, codes and referrals all work already.

1. **Create a Stripe account** at dashboard.stripe.com, then activate it (business details and bank account for payouts). You can start in **Test mode**.
2. **Create the product**: Products → Add product → "QuizlyNotes Pro", with two recurring prices:
   - £4.99 GBP, monthly
   - £29.99 GBP, yearly

   Copy both price IDs (`price_...`).
3. **Customer portal**: Settings → Billing → Customer portal → turn on "Cancel subscriptions", "Switch plans" (add both prices) and "Update payment methods". Save.
4. **Webhook**: Developers → Webhooks → Add endpoint
   - URL: `https://quizlynotes.com/billing/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`

   Copy the signing secret (`whsec_...`).
5. **Copy the secret key** from Developers → API keys (`sk_live_...` or `sk_test_...`).
6. **Optional, recommended**: Settings → Tax → turn on Stripe Tax if you register for VAT, and turn on Stripe's automatic emails for receipts and failed payments.
7. **Give the values to Cloud Run.** Send me a fresh `gcloud auth print-access-token` and I'll store them in Secret Manager. Or do it yourself:
   ```bash
   printf '%s' 'sk_live_...' | gcloud secrets create stripe-secret-key --data-file=-
   printf '%s' 'whsec_...'   | gcloud secrets create stripe-webhook-secret --data-file=-
   gcloud secrets add-iam-policy-binding stripe-secret-key --member=serviceAccount:101681370389-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor
   gcloud secrets add-iam-policy-binding stripe-webhook-secret --member=serviceAccount:101681370389-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor
   gcloud run services update flask-app --region europe-west1 \
     --update-secrets STRIPE_SECRET_KEY=stripe-secret-key:latest,STRIPE_WEBHOOK_SECRET=stripe-webhook-secret:latest \
     --update-env-vars STRIPE_PRICE_MONTHLY=price_...,STRIPE_PRICE_YEARLY=price_...,ADMIN_EMAILS=joefergsn@gmail.com
   ```
8. **Test**: in Test mode, buy Pro with card `4242 4242 4242 4242`, then check that Settings shows "Pro (yearly)" and that "Manage subscription" opens Stripe's portal.

## Things to watch after launch
- **Conversion**: aim for 3 to 5% of active free users on Pro within a few months. If it's lower, try 3 free sets instead of 5, or move up to 60 questions into Pro only. If signups stall, loosen the limits.
- **AI costs**: about 2 to 5p per set on Gemini Flash. 5 free sets a month means at most about 25p per free user. Pro's fair-use cap (300) protects you from abuse.
- **Exam seasons** (Dec/Jan, Apr to Jun): good moments for a promo code campaign, such as 30% off yearly via a Stripe coupon.
- **Legal**: the terms and privacy pages were updated for subscriptions and Stripe. Have them checked before taking real payments, and register for VAT once UK turnover approaches the threshold.
