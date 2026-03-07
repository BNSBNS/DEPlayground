# Math Foundations for AI/ML — Revised & Corrected 14-Week Plan

---

## How This Plan Works

```
TOTAL DURATION: 14 weeks
TIME COMMITMENT: 30-45 min/day weekdays + 1-2 hours on weekend
APPROACH: Visual intuition first → notation second → apply to ML third
```

### The Three-Layer Method

For EACH math concept:

```
Layer 1: VISUAL INTUITION (watch)
  → 3Blue1Brown or StatQuest video
  → Goal: "I can picture what this does in my head"

Layer 2: NOTATION LITERACY (read + practice)
  → Khan Academy exercises OR textbook problems
  → Goal: "I can read a formula and know what it's saying"

Layer 3: ML CONNECTION (apply)
  → Map the concept to something you already use at work
  → Goal: "I now understand WHY this parameter/algorithm works"
```

### Textbook Fallbacks

Videos are the primary resource, but if any link breaks or you want
deeper treatment, these textbooks cover the same material:

```
Phase 1 (Probability & Stats):
  → Sheldon Ross, "A First Course in Probability" (Chapters 1-5)
  → Or: Think Stats by Allen Downey (free online — code-first approach)

Phase 2 (Linear Algebra & Calculus):
  → Gilbert Strang, "Introduction to Linear Algebra" (Chapters 1-6)
  → Or: MIT OCW 18.06 (Strang's lectures, free on YouTube)
  → For calculus: James Stewart, "Calculus: Early Transcendentals" (Ch 2-3)

Phase 3 (Applied ML Math):
  → Kevin Murphy, "Probabilistic Machine Learning: An Introduction" (selected chapters)
  → Or: Bishop, "Pattern Recognition and Machine Learning" (Ch 1-4)
```

---

## Diagnostic: Where Are You?

Before starting, honestly check which of these you're comfortable with.
Start the plan at the first section where you score below 3/5.

```
SECTION A — Algebra & Functions
  [ ] I know what y = mx + b means and can plot it           /5
  [ ] I understand what a function is (input → output)       /5
  [ ] I can read summation notation: Σ                       /5
  [ ] I understand logarithms (log, ln) conceptually         /5

SECTION B — Probability & Statistics
  [ ] I can explain mean, median, standard deviation          /5
  [ ] I understand what a probability distribution is         /5
  [ ] I can explain Bayes' theorem in plain English           /5
  [ ] I know what a p-value means (roughly)                   /5

SECTION C — Linear Algebra
  [ ] I know what a matrix is and can multiply two matrices   /5
  [ ] I understand what a vector is (direction + magnitude)   /5
  [ ] I can explain what an eigenvalue/eigenvector is         /5
  [ ] I understand what a dot product represents              /5

SECTION D — Calculus
  [ ] I understand what a derivative means (rate of change)   /5
  [ ] I can explain gradient descent conceptually             /5
  [ ] I know what a partial derivative is                     /5
  [ ] I understand chain rule (at least the concept)          /5

If you scored mostly 1-2: Start from Week 1
If you scored mostly 3 in A/B but low in C/D: Start from Week 5
  ⚠ BUT: still complete the Phase 1 GATE checkpoint before starting
  Phase 2. Phase 2's exercises use probability and cross-entropy from
  Phase 1. If you can't pass the gate, go back.
If you scored 3+ everywhere but want depth: Start from Week 11
  ⚠ BUT: still complete the Phase 2 GATE. Same logic.
```

---

## PHASE 1: ALGEBRA + PROBABILITY (Weeks 1–4)
### The language ML speaks

---

### Week 1: Algebra Refresher — Functions, Notation, Logs

**Why this matters for ML:**
Every ML algorithm is a function. Linear regression is y = wx + b.
Neural networks are nested functions. Loss functions, activation functions,
cost functions — it's functions all the way down. If the notation feels
alien, every paper and course becomes a wall.

```
WATCH (Layer 1 — intuition):
├── 3Blue1Brown: "Essence of Calculus" — Chapter 1 only (17 min)
│   → youtube.com/watch?v=WUvTyaaNkzM
│   → Don't worry about calculus yet. This video re-introduces
│     functions visually: input → transformation → output
│
├── Khan Academy: "Introduction to Logarithms" (10 min)
│   → khanacademy.org/math/algebra2/x2ec2f6f830c9fb89:logs
│   → log(x) = "what power do I raise the base to, to get x?"
│   → ln(x) = log base e. Shows up EVERYWHERE in ML:
│     - log loss (binary cross-entropy)
│     - log-likelihood
│     - log transformations for skewed features
│     - softmax denominator

PRACTICE (Layer 2 — notation):
├── Khan Academy "Algebra 2" exercises — pick 3-4 topics:
│   → Functions and their graphs
│   → Logarithms
│   → Summation notation (Σ)
│   → Spend ~30 min/day on exercises. Get 80%+ before moving on.
│
├── NOTATION DRILL — translate these from math to English:
│
│   ŷ = wx + b
│   → "predicted value = weight times input plus bias"
│   → This is linear regression. You've used it.
│
│   Σᵢ₌₁ⁿ xᵢ / n
│   → "add up all x values, divide by count" → that's the mean
│   → df['Amount'].mean() does exactly this
│
│   J(w) = (1/n) Σᵢ₌₁ⁿ (ŷᵢ - yᵢ)²
│   → "average of squared differences between predictions and actuals"
│   → This is Mean Squared Error (MSE)
│   → sklearn.metrics.mean_squared_error computes exactly this
│   → NOTE: You'll sometimes see (1/2n) instead of (1/n). The 1/2 is
│     a convenience — it makes the derivative cleaner (the 2 from the
│     power rule cancels with the 1/2). The formula with (1/2n) is
│     the "cost function J," not MSE proper. sklearn uses (1/n).
│
│   log(p / (1-p))
│   → "log-odds" — this is what logistic regression actually models
│   → When you call LogisticRegression().fit(), this is the internal math

ML CONNECTION (Layer 3):
└── Open one of your existing models. Find where these show up:
    → Loss function: what formula is being minimized?
    → Learning rate: it multiplies the gradient. What's the gradient?
    → Regularization parameter: why does adding |w| or w² help?
    You don't need to answer fully yet. Just notice the notation.
```

#### ✅ Week 1 Checkpoint Exercise

```
Translate each formula into plain English AND identify the Python
equivalent. Write your answers BEFORE checking below.
Then VERIFY in Python (this matters — start building the habit
of checking your math against code).

1)  f(x) = 3x² + 2x - 1
    Plain English: _______________
    Python: _______________

2)  Σᵢ₌₁⁵ i² = ?
    Compute by hand: _______________
    Verify in Python: _______________

3)  log₂(32) = ?
    Answer: _______________
    Why: _______________

4)  ln(e³) = ?
    Answer: _______________
    Why: _______________

5)  Compute MSE by hand for these predictions and actuals:
    ŷ = [2.0, 3.5, 1.0]
    y = [2.5, 3.0, 1.5]
    MSE = (1/3)[(2.0-2.5)² + (3.5-3.0)² + (1.0-1.5)²] = ___
    Verify: from sklearn.metrics import mean_squared_error
            mean_squared_error([2.5, 3.0, 1.5], [2.0, 3.5, 1.0])

--- ANSWERS ---

1)  "A function that takes x, squares it, triples it, adds twice x,
     then subtracts 1"
    Python: def f(x): return 3*x**2 + 2*x - 1

2)  1² + 2² + 3² + 4² + 5² = 1 + 4 + 9 + 16 + 25 = 55
    Python: sum(i**2 for i in range(1, 6))  # verify: 55

3)  log₂(32) = 5, because 2⁵ = 32.
    "What power of 2 gives me 32?"

4)  ln(e³) = 3, because ln is log base e, and logₑ(e³) = 3.
    Natural log and e are inverses.

5)  MSE = (1/3)(0.25 + 0.25 + 0.25) = 0.25

PASS CRITERIA: Get at least 4 of 5 correct, AND verify at least
one answer in Python, before moving to Week 2.
```

---

### Week 2: Probability — Joint Distributions, Conditional Probability, and Bayes

**Why this matters for ML:**
Every model output is a probability. predict_proba, softmax, sigmoid,
Bayesian methods, confidence intervals — all probability.
If you don't grok probability, you're using these outputs without
understanding what they actually mean.

**DESIGN NOTE:** We start with expected value, joint distributions,
and conditional independence BEFORE Bayes' theorem. You can't properly
understand P(A|B) = P(A,B)/P(B) if you haven't spent time with P(A,B)
first. Bayes becomes a natural consequence rather than a formula to
memorize.

```
WATCH (Layer 1):
├── Khan Academy: "Joint and Marginal Distributions" (series)
│   → P(A, B) = "probability of A AND B happening together"
│   → P(A) = Σ_B P(A, B) = "marginalize out B" = "sum over all possible B values"
│   → This is the foundation. Everything below builds on it.
│
├── 3Blue1Brown: "Bayes' theorem" (17 min)
│   → youtube.com/watch?v=HZGCoVF3YvM
│   → Watch this one twice. It's that important.
│   → Bayes = "how to update beliefs with evidence"
│   → This is literally what model training does
│
├── StatQuest: "The Normal Distribution" (5 min)
├── StatQuest: "P-values" (11 min)

PRACTICE (Layer 2):
├── Khan Academy: "Probability" section
│   → Joint probability, marginal probability, conditional probability
│   → Bayes' theorem
│   → 30 min/day exercises
│
├── CORE DEFINITIONS YOU NEED:
│
│   EXPECTED VALUE:
│   E[X] = Σ x · P(x)
│   → "The weighted average outcome, where weights are probabilities"
│   → For discrete X: multiply each value by its probability, sum up
│   → For a fair die: E[X] = 1·(1/6) + 2·(1/6) + ... + 6·(1/6) = 3.5
│   → In ML: "expected loss" = average loss over all possible data
│   → df['Amount'].mean() approximates E[Amount] from the data
│
│   VARIANCE:
│   Var(X) = E[(X - μ)²] = E[X²] - (E[X])²
│   → "How spread out the values are, on average"
│   → The second formula is computationally easier (compute E[X²] and E[X]
│     separately, then subtract)
│   → Standard deviation σ = sqrt(Var(X))
│   → These definitions are needed for the bias-variance decomposition
│     in Week 12 — that decomposition is DEFINED in terms of expectations
│     over different training sets
│
├── NOTATION DRILL:
│
│   P(A, B) = P(A|B) · P(B)
│   → "Joint probability = conditional times marginal"
│   → This is the PRODUCT RULE. Everything in probability derives from this.
│
│   P(A) = Σ_B P(A, B)
│   → Marginalization. "Sum out" the variable you don't care about.
│   → In fraud detection: P(high_amount) = P(high_amount, fraud) + P(high_amount, legit)
│
│   CONDITIONAL INDEPENDENCE:
│   P(A, B | C) = P(A|C) · P(B|C)
│   → "Given C, knowing A tells you nothing extra about B"
│   → This is the core assumption of Naive Bayes:
│     P(x₁, x₂, ..., xₙ | class) = Π P(xᵢ | class)
│   → "Features are independent given the class label"
│   → This is also why correlated features are problematic in many models —
│     they violate this assumption, inflating the evidence for a class.
│   → NOTE: conditional independence ≠ independence.
│     Two features can be dependent overall but independent given the class.
│
│   P(A|B) = P(B|A) · P(A) / P(B)
│   → Bayes' theorem — derived directly from the product rule:
│     P(A,B) = P(A|B)·P(B) = P(B|A)·P(A)  →  solve for P(A|B)
│   → In fraud detection: P(fraud | features) = P(features | fraud) · P(fraud) / P(features)
│   → P(fraud) is the "prior" — 0.17% in the credit card dataset
│   → This is WHY class imbalance matters mathematically
│
│   PROBABILITY vs LIKELIHOOD — getting this right matters:
│   These are the SAME mathematical expression, viewed differently.
│
│   P(x | θ) as a function of x (with θ fixed) = PROBABILITY
│   → "Given these model parameters, how probable is this data?"
│   → You're asking about different possible data.
│
│   L(θ | x) = P(x | θ) as a function of θ (with x fixed) = LIKELIHOOD
│   → "Given this observed data, how 'likely' are these parameters?"
│   → You're asking about different possible parameters.
│   → The data x is fixed (you already observed it).
│   → Same formula. Different question. Different name.
│
│   WHAT LIKELIHOOD IS NOT:
│   → L(θ|x) is NOT P(θ|x). That's the POSTERIOR — the probability
│     of the parameters given the data. The posterior is what Bayes'
│     theorem computes: P(θ|x) ∝ P(x|θ) · P(θ) = likelihood × prior
│   → Confusing likelihood with the posterior is the #1 probability
│     mistake in ML. If someone says "the likelihood of the model
│     given the data," they almost always mean "the likelihood of
│     the parameters," which is P(data | parameters), NOT P(parameters | data).
│
│   σ = sqrt( Σ(xᵢ - μ)² / (n-1) )
│   → Standard deviation. μ = mean. Note: n-1 (Bessel's correction),
│     not n. This corrects for the bias when estimating from a sample.
│   → df.std() uses n-1 by default.
│   → Z-score = (x - μ) / σ → "how many standard deviations from the mean"
│
│   P(y=1|x) = 1 / (1 + e^(-z))    where z = wx + b
│   → The sigmoid function. This IS logistic regression.
│   → Input z can be any real number (-∞ to +∞)
│   → Output is always between 0 and 1 (a probability)
│   → When z = 0: probability = 0.5 (decision boundary)
│   → LogisticRegression().predict_proba() computes exactly this

ML CONNECTION (Layer 3):
├── Take a trained logistic regression model
│   → Extract coefficients: model.coef_, model.intercept_
│   → For one sample, manually compute: z = coef · features + intercept
│   → Apply sigmoid: 1 / (1 + exp(-z))
│   → Compare to model.predict_proba(sample)
│   → They should match. You just did logistic regression BY HAND.
│
└── This exercise is the single best way to demystify model internals.
    When you can reproduce the model's output with your own math,
    the math stops being scary and starts being a tool.
```

#### ✅ Week 2 Checkpoint Exercise

```
EXPECTED VALUE:

0)  A random variable X takes values {1, 2, 3} with probabilities
    {0.5, 0.3, 0.2}. Compute E[X] and Var(X).
    E[X] = 1(0.5) + 2(0.3) + 3(0.2) = ___
    E[X²] = 1²(0.5) + 2²(0.3) + 3²(0.2) = ___
    Var(X) = E[X²] - (E[X])² = ___

BAYES' THEOREM:

SCENARIO: You have a medical test for a rare disease.
  - P(disease) = 0.01         (1% of the population has it)
  - P(positive | disease) = 0.95   (test catches 95% of sick people)
  - P(positive | no disease) = 0.05 (test falsely alarms 5% of healthy people)

1)  What is P(positive)?
    Hint: Use marginalization.
    P(positive) = P(positive|disease)·P(disease) + P(positive|no disease)·P(no disease)
    Compute: _______________

2)  What is P(disease | positive)?
    Use Bayes' theorem.
    Compute: _______________

3)  Explain in plain English: if someone tests positive,
    what's the chance they actually have the disease?
    Answer: _______________

4)  How does this connect to fraud detection with 0.17% fraud rate?
    Answer: _______________

LIKELIHOOD:

5)  You observe data x = [3, 5, 7]. You have a model with parameter θ.
    P(x|θ=2) = 0.01   and   P(x|θ=5) = 0.08
    Which value of θ has higher likelihood? Why?
    Is L(θ=5|x) = 0.08 the probability that θ=5? Why or why not?
    Answer: _______________

--- ANSWERS ---

0)  E[X] = 0.5 + 0.6 + 0.6 = 1.7
    E[X²] = 0.5 + 1.2 + 1.8 = 3.5
    Var(X) = 3.5 - 1.7² = 3.5 - 2.89 = 0.61

1)  P(positive) = 0.95 × 0.01 + 0.05 × 0.99
                = 0.0095 + 0.0495 = 0.059

2)  P(disease | positive) = P(positive|disease) · P(disease) / P(positive)
                           = 0.95 × 0.01 / 0.059
                           = 0.0095 / 0.059
                           ≈ 0.161 (about 16.1%)

3)  Even with a 95% accurate test, a positive result only means a 16%
    chance of actually having the disease. The low base rate (1%)
    dominates. Most positives are false positives.

4)  With 0.17% fraud, the same math applies even more severely.
    A model predicting "fraud" will generate many false positives
    unless it's extremely precise. This is why we use precision-recall
    curves instead of accuracy for imbalanced classes — accuracy
    of 99.83% is trivially achieved by predicting "not fraud" always.

5)  θ=5 has higher likelihood (0.08 > 0.01). The likelihood tells us
    which parameter value makes the observed data more probable.
    But L(θ=5|x) = 0.08 is NOT the probability that θ=5. It's
    P(data | θ=5) — the probability of the data given θ=5. To get
    the probability of θ=5 given the data, you'd need Bayes' theorem:
    P(θ=5|x) ∝ P(x|θ=5) · P(θ=5) = likelihood × prior.
    Likelihood and posterior are different things.

PASS CRITERIA: If you can explain #3, #4, and #5 without looking at
the answers, you've internalized the probability foundations.
```

---

### Week 3: Probability Distributions + Maximum Likelihood

**Why this matters for ML:**
When you choose a loss function, you're implicitly choosing a probability
distribution. MSE assumes Gaussian errors. Log loss assumes Bernoulli.
Understanding distributions = understanding loss functions.

```
WATCH (Layer 1):
├── StatQuest: "Probability Distributions" (5 min)
├── StatQuest: "Maximum Likelihood" (6 min)
│   → This is THE core concept: "find the parameters that make the
│     observed data most probable"
│   → model.fit() = "find maximum likelihood estimates"
│
├── StatQuest: "Cross-Entropy / Log Loss" (11 min)
│   → Binary cross-entropy is THE fraud detection loss function
│   → XGBoost's binary:logistic objective = minimizing cross-entropy

PRACTICE (Layer 2):
├── Khan Academy: "Random variables and distributions"
│   → Normal (Gaussian), Bernoulli, Binomial
│   → 30 min/day
│
├── NOTATION DRILL:
│
│   L(θ|x) = Πᵢ₌₁ⁿ P(xᵢ|θ)
│   → Likelihood function. Π = product (multiply all terms).
│   → "How probable is this data, under these parameters?"
│   → We want to FIND the θ that maximizes this. That's MLE.
│   → We usually take the log (easier math):
│     log L(θ|x) = Σᵢ₌₁ⁿ log P(xᵢ|θ)
│   → Product becomes sum. This is why we use "log" likelihood.
│   → WHY logs? Two reasons:
│     1. NUMERICAL STABILITY: Products of tiny probabilities underflow
│        to 0.0 in floating point. With 10,000 samples and each
│        P(xᵢ|θ) < 1, the product becomes ~10⁻⁴⁰⁰⁰ → exactly 0.
│        Sums of log-probabilities stay in computable range.
│        (This is your first taste of numerical stability — we'll
│        cover more in Week 13.)
│     2. MATHEMATICAL CONVENIENCE: Sums are easier to differentiate
│        than products. The derivative of a sum = sum of derivatives.
│
│   Loss = -Σ[yᵢ·log(pᵢ) + (1-yᵢ)·log(1-pᵢ)]
│   → Binary cross-entropy (log loss)
│   → y=1 (fraud): loss comes from -log(p) → penalizes low probability for fraud
│   → y=0 (legit): loss comes from -log(1-p) → penalizes high probability for legit
│   → XGBoost with binary:logistic is minimizing exactly this
│   → IMPORTANT: log(0) is undefined (-infinity). In practice,
│     implementations use log(p + ε) where ε ≈ 1e-15 to avoid this.

ML CONNECTION (Layer 3):
└── Train an XGBoost model with eval_metric='logloss' and verbose=True
    → Watch the loss decrease each iteration
    → Each iteration = one step of "making the data more likely under the model"
    → The loss number you see IS the cross-entropy formula above
```

#### ✅ Week 3 Checkpoint Exercise

```
MAXIMUM LIKELIHOOD — DERIVE IT, DON'T JUST PLUG IN:

You flip a coin 10 times and get: H H T H T H H H T H (7 heads, 3 tails).
The coin has some unknown probability p of landing heads.

1)  Write the likelihood function L(p).
    Hint: Each flip is independent Bernoulli.
    L(p) = _______________

2)  Write the log-likelihood.
    log L(p) = _______________

3)  NOW DERIVE the MLE. Take the derivative of the log-likelihood
    with respect to p, set it to zero, and solve:
    d/dp [log L(p)] = d/dp [7·log(p) + 3·log(1-p)]
                    = 7/p + 3·(-1)/(1-p)
                    = 7/p - 3/(1-p) = 0

    Solve for p:
    7/p = 3/(1-p)
    7(1-p) = 3p
    7 - 7p = 3p
    7 = 10p
    p_hat = ___

    This is 3 lines of calculus that preview Week 9. If the derivatives
    feel foreign, just follow the algebra — you'll revisit derivatives
    properly in Week 9.

4)  Verify: does p_hat = (number of heads) / (total flips)?
    This is a general result for Bernoulli: the MLE is always the
    sample proportion. You just proved it.

5)  Now connect to ML: when sklearn's LogisticRegression runs .fit(),
    it's doing the same thing — finding parameters that maximize
    the likelihood of the observed labels. The difference is that
    the "coin" has features that affect its bias, and the derivative
    is more complex (involves the sigmoid function).

CROSS-ENTROPY BY HAND:

Given these predictions and actuals:
  predictions = [0.9, 0.1, 0.8, 0.3, 0.95]
  actuals     = [1,   0,   1,   1,   0   ]

6)  Compute the loss for each sample:
    L = -[y·log(p) + (1-y)·log(1-p)]
    Sample 1: -[1·log(0.9) + 0·log(0.1)]   = -log(0.9)   ≈ ___
    Sample 2: -[0·log(0.1) + 1·log(0.9)]   = -log(0.9)   ≈ ___
    Sample 3: -[1·log(0.8) + 0·log(0.2)]   = -log(0.8)   ≈ ___
    Sample 4: -[1·log(0.3) + 0·log(0.7)]   = -log(0.3)   ≈ ___
    Sample 5: -[0·log(0.95) + 1·log(0.05)] = -log(0.05)  ≈ ___

    Verify in Python:
    import numpy as np
    preds = np.array([0.9, 0.1, 0.8, 0.3, 0.95])
    labels = np.array([1, 0, 1, 1, 0])
    losses = -(labels*np.log(preds) + (1-labels)*np.log(1-preds))
    print(losses)

7)  Which sample has the WORST loss? Why?

--- ANSWERS ---

1)  L(p) = p⁷ · (1-p)³
    (probability of 7 heads times probability of 3 tails)

2)  log L(p) = 7·log(p) + 3·log(1-p)

3)  p_hat = 7/10 = 0.7

4)  Yes: 7 heads / 10 flips = 0.7. The MLE for a Bernoulli is always
    the observed frequency. You derived this from first principles.

6)  Sample 1: -log(0.9)  ≈ 0.105
    Sample 2: -log(0.9)  ≈ 0.105
    Sample 3: -log(0.8)  ≈ 0.223
    Sample 4: -log(0.3)  ≈ 1.204
    Sample 5: -log(0.05) ≈ 2.996

7)  Sample 5 is worst (loss ≈ 3.0). The model predicted 95% confidence
    in class 1, but the actual was class 0. Confident WRONG predictions
    are punished severely by log loss. This is by design — the -log
    curve shoots to infinity as p approaches 0.

PASS CRITERIA: You should be able to (a) derive the Bernoulli MLE
by taking the derivative of the log-likelihood, and (b) compute
cross-entropy for any (prediction, actual) pair without looking at notes.
```

---

### Week 4: Statistics for Model Evaluation

**Why this matters for ML:**
Confidence intervals, hypothesis testing, cross-validation — these
answer the question "is this result real or just noise?"
Without this, you can't tell if model A is actually better than model B,
or if the difference is random chance.

```
WATCH (Layer 1):
├── StatQuest: "Confidence Intervals" (6 min)
├── StatQuest: "Hypothesis Testing and P-values" (11 min)
├── StatQuest: "The Central Limit Theorem" (6 min)

PRACTICE (Layer 2):
├── Khan Academy: "Confidence intervals" + "Hypothesis testing" sections
│
├── NOTATION DRILL:
│
│   CI = x̄ ± t · (s / √n)
│   → Confidence interval for a mean
│   → x̄ = sample mean, s = sample standard deviation
│   → t = t-score for confidence level (from t-distribution)
│   → NOTE: We use t and s (not z and σ) because in practice you
│     almost never know the true population σ. You estimate it
│     with the sample standard deviation s, which requires the
│     t-distribution. For large n (>30), t ≈ z and they converge.
│   → Bigger n (more data) → narrower CI → more certain
│
│   AUC-PR = ∫ precision(r) dr  (over recall values)
│   → Area Under Precision-Recall Curve
│   → Integral just means "area under the curve"
│   → eval_metric='aucpr' in XGBoost computes this
│   → Higher is better. 1.0 = perfect. Baseline ≈ fraud rate (0.0017)

ML CONNECTION (Layer 3):
├── Run 5-fold cross-validation on your fraud detector
│   → sklearn.model_selection.cross_val_score
│   → You get 5 F1 scores. Calculate mean and standard deviation.
│   → "My model achieves 0.84 ± 0.03 F1 across 5 folds"
│   → That ± IS a confidence-like statement. The std tells you
│     how stable the model is across different data splits.
│
└── Compare two models using cross-validation:
    → If Model A: 0.84 ± 0.03 and Model B: 0.86 ± 0.05
    → Is B actually better? The ranges overlap.
    → You'd want a statistical test to be sure. But be careful:
      a simple paired t-test on 5 fold scores has known problems —
      the folds share ~75% of their training data, so they're NOT
      independent, which inflates the t-test's confidence.
    → Better approaches: the corrected resampled t-test (Nadeau &
      Bengio, 2003) or the 5×2 CV test (Dietterich, 1998).
    → The key insight: "my model looks better" ≠ "my model IS better."
      Small differences on few folds are often noise.
```

#### ✅ Week 4 Checkpoint Exercise

```
CROSS-VALIDATION REASONING:

You ran 5-fold CV on three models and got these F1 scores:

  Model A: [0.82, 0.85, 0.83, 0.84, 0.81]  → mean=0.830, std=0.015
  Model B: [0.78, 0.91, 0.80, 0.88, 0.73]  → mean=0.820, std=0.072
  Model C: [0.86, 0.87, 0.85, 0.86, 0.86]  → mean=0.860, std=0.007

1)  Which model would you deploy in production? Why?
    Consider both mean performance AND stability.
    Answer: _______________

2)  Model B has a fold with 0.91 — the best single score.
    Why is this NOT a reason to pick Model B?
    Answer: _______________

3)  Model C has a lower maximum (0.87) than Model B (0.91).
    Why is Model C still preferable?
    Answer: _______________

4)  You want to know if Model C is statistically significantly
    better than Model A. Why is a simple paired t-test on 5
    fold scores problematic? What would you do instead?
    Answer: _______________

Verify in Python:
  import numpy as np
  a = np.array([0.82, 0.85, 0.83, 0.84, 0.81])
  c = np.array([0.86, 0.87, 0.85, 0.86, 0.86])
  print(f"A: {a.mean():.3f} ± {a.std():.3f}")
  print(f"C: {c.mean():.3f} ± {c.std():.3f}")
  print(f"Differences: {c - a}")

--- ANSWERS ---

1)  Model C. It has the highest mean (0.860) AND the lowest
    variance (std=0.007). It performs consistently well regardless
    of which data split it sees.

2)  High variance means B is unreliable. Its performance depends
    heavily on which data it sees. A 0.91 on one fold and 0.73
    on another means it might perform anywhere in that range in
    production. You can't predict which you'll get.

3)  Stability matters more than peak performance in production.
    Model C's worst case (0.85) is better than Model B's worst
    case (0.73). You want predictable, reliable performance.

4)  A paired t-test on 5 fold scores has two problems:
    (a) n=5 gives very low statistical power — you're unlikely to
        detect a real difference even if one exists.
    (b) The folds are NOT independent — each fold's training set
        overlaps ~75% with every other fold's training set. This
        violates the t-test's independence assumption and inflates
        the false positive rate (you'll declare significance when
        there isn't any).
    Better: use the corrected resampled t-test (which adjusts the
    variance estimate for the overlap), or run a 5×2 CV test
    (5 repetitions of 2-fold CV, which has less overlap).
    In practice: if the difference is small and folds are few,
    acknowledge the uncertainty rather than claiming significance.

PASS CRITERIA: You should be able to explain why variance matters
as much as the mean, and why naive statistical testing on CV folds
can mislead you.
```

---

## 🏁 PHASE 1 GATE — Complete Before Moving On

```
Before starting Phase 2, verify you can do ALL of the following
WITHOUT looking at notes:

[ ] Read Σ and Π notation and explain what they compute
[ ] Define expected value E[X] and variance Var(X)
[ ] Explain Bayes' theorem using the product rule: P(A|B) = P(A,B)/P(B)
[ ] Explain the difference between likelihood and posterior
    (L(θ|x) = P(x|θ) is NOT the same as P(θ|x))
[ ] Explain why low base rates cause high false positive rates
[ ] Manually compute logistic regression output from coefficients
[ ] Derive the Bernoulli MLE from the log-likelihood derivative
[ ] Compute cross-entropy loss for a (prediction, actual) pair
[ ] Explain why accuracy is misleading for imbalanced classes (mathematically)
[ ] Explain why we use log-likelihood instead of likelihood (two reasons)

If you can't pass 8/10 of these, spend an extra week on Phase 1.
Depth here prevents confusion in every later phase.
```

---

## PHASE 2: LINEAR ALGEBRA + CALCULUS (Weeks 5–10)
### The math behind data transformations, optimization, and neural networks

---

### Week 5: Vectors, Matrices, and Transpose — What Your Data Actually Is

**Why this matters for ML:**
Your DataFrame IS a matrix. Each row is a vector. Feature scaling,
PCA, embeddings, attention mechanisms — all matrix operations.
Understanding this changes how you think about data.

```
WATCH (Layer 1):
├── 3Blue1Brown: "Essence of Linear Algebra" series
│   → Watch 2-3 per day, they're short
│   → This week focus on:
│     Ch 1: Vectors — what are they really?
│     Ch 3: Linear transformations and matrices
│     Ch 4: Matrix multiplication as composition
│     Ch 7: Dot products and duality
│   → After these 4, you'll see matrices differently.
│
│   KEY INSIGHT from 3B1B:
│   A matrix is NOT "a grid of numbers."
│   A matrix is a TRANSFORMATION — it moves, stretches, or rotates space.
│   Matrix multiplication = applying one transformation after another.
│   A neural network layer = a matrix transformation followed by an activation.
│   That's it. That's what a layer does.

PRACTICE (Layer 2):
├── Khan Academy: "Vectors and spaces" + "Matrix transformations"
│   → Focus on: vector addition, scalar multiplication, dot product,
│     matrix-vector multiplication, matrix-matrix multiplication
│   → 30 min/day exercises
│
├── NOTATION DRILL:
│
│   X ∈ ℝⁿˣᵐ
│   → "X is a matrix of real numbers with n rows and m columns"
│   → Your fraud dataset: X ∈ ℝ²⁸⁴⁸⁰⁷ˣ³⁰
│
│   TRANSPOSE:
│   If A is an m×n matrix, then Aᵀ ("A transpose") is the n×m matrix
│   obtained by swapping rows and columns.
│   → Row i of A becomes column i of Aᵀ.
│   → If A = [[1, 2, 3],    then Aᵀ = [[1, 4],
│              [4, 5, 6]]               [2, 5],
│                                        [3, 6]]
│   → KEY PROPERTIES:
│     (Aᵀ)ᵀ = A                    (transpose twice = back to original)
│     (AB)ᵀ = BᵀAᵀ                 (transpose of product = reversed product of transposes)
│     (A + B)ᵀ = Aᵀ + Bᵀ          (transpose distributes over addition)
│   → In numpy: X.T or np.transpose(X)
│   → You need this because Xᵀ appears in: the normal equation,
│     the covariance matrix, dot product as matrix multiplication,
│     and throughout the XGBoost paper.
│
│   WHY TRANSPOSE MATTERS FOR ML:
│   → xᵀw = dot product of x and w (row vector × column vector = scalar)
│   → XᵀX = a square matrix (n_features × n_features) even when X isn't square
│     This is WHY the normal equation works: X is (n_samples × n_features),
│     XᵀX is (n_features × n_features) → can be inverted (if full rank)
│   → Xᵀy = the "match" between features and target (n_features × 1)
│
│   w · x = Σᵢ wᵢxᵢ = w₁x₁ + w₂x₂ + ... + wₙxₙ
│   → Dot product. This is what a single neuron computes.
│   → Equivalently: wᵀx (transpose of w times x, matrix notation)
│   → Linear regression prediction = wᵀx + b = w · x + b
│   → np.dot(w, x) does this
│
│   Xw = ŷ
│   → Matrix-vector multiplication. Predicts ALL samples at once.
│   → X is (n_samples × n_features), w is (n_features × 1)
│   → Result ŷ is (n_samples × 1) — one prediction per sample
│   → model.predict() does this matrix multiplication internally

ML CONNECTION (Layer 3):
└── In Python, verify these equivalences:
    import numpy as np
    w = np.array([0.5, -0.3])
    x = np.array([2.0, 4.0])
    # These all compute the same thing:
    print(np.dot(w, x))       # dot product
    print(w @ x)              # matrix multiplication operator
    print(np.sum(w * x))      # element-wise multiply then sum
    print(w.T @ x)            # transpose notation (1D arrays: same result)
```

#### ✅ Week 5 Checkpoint Exercise

```
MATRIX OPERATIONS BY HAND — then verify in Python:

Given:
  A = [[1, 2],    B = [[5, 6],    v = [3,
       [3, 4]]         [7, 8]]         1]

1)  Compute A · v (matrix-vector multiplication):
    Row 1: 1×3 + 2×1 = ___
    Row 2: 3×3 + 4×1 = ___
    Result: ___

2)  Compute A · B (matrix-matrix multiplication):
    Row 1, Col 1: 1×5 + 2×7 = ___
    Row 1, Col 2: 1×6 + 2×8 = ___
    Row 2, Col 1: 3×5 + 4×7 = ___
    Row 2, Col 2: 3×6 + 4×8 = ___
    Result: ___

3)  What is Aᵀ? ___
    What are the dimensions of A? ___  Of Aᵀ? ___

4)  Compute AᵀA:
    Aᵀ = [[1, 3], [2, 4]]
    AᵀA = [[1×1+3×3, 1×2+3×4], [2×1+4×3, 2×2+4×4]]
         = ___
    Note: AᵀA is square and symmetric. This will matter for Week 7 (PCA).

5)  Verify ALL of the above in Python:
    import numpy as np
    A = np.array([[1,2],[3,4]]); B = np.array([[5,6],[7,8]]); v = np.array([3,1])
    print(A @ v); print(A @ B); print(A.T); print(A.T @ A)

--- ANSWERS ---

1)  [5, 13]
2)  [[19, 22], [43, 50]]
3)  Aᵀ = [[1, 3], [2, 4]].  A is 2×2. Aᵀ is 2×2 (square matrices transpose to same size).
4)  AᵀA = [[10, 14], [14, 20]]
    Verify it's symmetric: element [0,1] = element [1,0] = 14. ✓

PASS CRITERIA: You can do 2×2 matrix multiplication without
hesitation, compute a transpose, and explain what Xᵀ does.
```

---

### Week 6: Linear Independence, Rank, and Invertibility

**Why this matters for ML:**
When you see the normal equation w = (XᵀX)⁻¹Xᵀy, the natural
question is "when does that inverse exist?" The answer is: when XᵀX
has full rank — when your features are linearly independent.
Multicollinearity breaks linear regression because it makes XᵀX
singular (non-invertible). This week gives you the vocabulary to
understand WHY.

```
WATCH (Layer 1):
├── 3Blue1Brown: "Essence of Linear Algebra" continued:
│     Ch 5: Three-dimensional linear transformations
│     Ch 6: The determinant
│     Ch 8: Inverse matrices, column space, and null space
│   → The determinant tells you if a transformation "squishes"
│     space to a lower dimension. det = 0 → non-invertible.
│
├── Khan Academy: "Linear independence" (series)

KEY CONCEPTS:
├── LINEAR INDEPENDENCE:
│   Vectors are linearly independent if none of them can be written
│   as a combination of the others.
│   → Features are linearly independent = no feature is a perfect
│     linear combo of other features
│   → If feature3 = 2×feature1 + feature2, you have multicollinearity
│   → (XᵀX) becomes singular → normal equation blows up
│   → VIF (Variance Inflation Factor) checks for this numerically
│
├── RANK:
│   Rank of a matrix = number of linearly independent rows (or columns).
│   → Full rank: all features carry unique information
│   → Rank-deficient: some features are redundant
│   → np.linalg.matrix_rank(X) tells you
│
├── INVERTIBILITY:
│   A matrix A is invertible if AA⁻¹ = I (identity matrix).
│   → Only square matrices can be inverted
│   → Only full-rank square matrices have inverses
│   → XᵀX is square (n_features × n_features)
│   → If rank(XᵀX) < n_features → not invertible → can't use normal equation
│
│   WHAT HAPPENS WHEN THE INVERSE DOESN'T EXIST?
│   → sklearn's LinearRegression doesn't actually use (XᵀX)⁻¹ directly.
│     It uses the Moore-Penrose pseudo-inverse via SVD (Singular Value
│     Decomposition).
│   → The pseudo-inverse generalizes the inverse to matrices that are
│     non-square or singular. It always exists and gives the minimum-norm
│     least-squares solution.
│   → In practice: np.linalg.lstsq(X, y) uses SVD internally and works
│     even when np.linalg.inv(X.T @ X) would crash.
│   → BUT: even though sklearn gives you an answer, the coefficients
│     will be unstable and uninterpretable when multicollinearity is
│     present. The pseudo-inverse "works" mathematically but the
│     solution isn't meaningful.
│
│   THE NORMAL EQUATION:
│   w = (XᵀX)⁻¹Xᵀy
│   → "The closed-form solution for linear regression"
│   → np.linalg.inv(X.T @ X) @ X.T @ y
│   → Works only if (XᵀX) is invertible (full rank, no multicollinearity)

PRACTICE (Layer 2):
├── Khan Academy: "Matrix inverses" + "Determinants"
│   → Focus on 2×2 and 3×3 cases
│   → Compute determinants by hand for small matrices
│   → det = 0 → not invertible. Build this intuition.

ML CONNECTION (Layer 3):
└── Linear regression from scratch:
    → w = (XᵀX)⁻¹Xᵀy (the normal equation)
    → Compare to sklearn's LinearRegression().fit().coef_
    → Verify in Python:
      import numpy as np
      from sklearn.linear_model import LinearRegression
      X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
      y = np.array([3, 7, 11, 15])
      # Normal equation:
      w = np.linalg.inv(X.T @ X) @ X.T @ y
      # sklearn:
      model = LinearRegression(fit_intercept=False).fit(X, y)
      print(w, model.coef_)  # should match
    → Now try adding a duplicate feature and watch it break:
      X_bad = np.column_stack([X, X[:, 0]])  # duplicate column 0
      np.linalg.inv(X_bad.T @ X_bad)  # LinAlgError: Singular matrix
```

#### ✅ Week 6 Checkpoint Exercise

```
TESTING YOUR UNDERSTANDING:

1)  Are these vectors linearly independent?
    v1 = [1, 0, 0]
    v2 = [0, 1, 0]
    v3 = [1, 1, 0]
    Answer: ___  Why: ___

2)  What is the rank of this matrix?
    M = [[1, 2, 3],
         [2, 4, 6],
         [0, 1, 1]]
    Answer: ___  Why: ___

3)  Is this matrix invertible?
    A = [[1, 2],
         [3, 4]]
    Compute det(A): ___
    Answer: ___

4)  Is this matrix invertible?
    B = [[1, 2],
         [2, 4]]
    Compute det(B): ___
    Answer: ___

5)  In your fraud dataset, if you accidentally include both
    "amount_usd" and "amount_cents" (= amount_usd × 100),
    what happens to linear regression? Why?
    What does sklearn actually DO in this case?

Verify #3 and #4 in Python:
    import numpy as np
    A = np.array([[1,2],[3,4]]); B = np.array([[1,2],[2,4]])
    print(np.linalg.det(A))  # should be -2
    print(np.linalg.det(B))  # should be ~0
    print(np.linalg.matrix_rank(B))  # should be 1

--- ANSWERS ---

1)  NO. v3 = v1 + v2. Three vectors in 3D CAN be independent,
    but these aren't because one is a linear combination of the others.

2)  Rank = 2. Row 2 = 2 × Row 1 (they're linearly dependent).
    Only 2 of the 3 rows carry unique information.

3)  det(A) = 1×4 - 2×3 = 4 - 6 = -2. Not zero → invertible.

4)  det(B) = 1×4 - 2×2 = 4 - 4 = 0. Zero → NOT invertible.
    Row 2 is exactly 2 × Row 1.

5)  amount_cents = 100 × amount_usd, so they're perfectly
    linearly dependent. XᵀX becomes singular (rank-deficient).
    The normal equation (XᵀX)⁻¹Xᵀy fails.
    sklearn uses SVD/pseudo-inverse internally, so it will still give
    you coefficients — but they'll be unstable. Run it twice with
    slightly different data and the individual coefficients for
    amount_usd and amount_cents will change wildly, even though
    their combined prediction stays similar. This is multicollinearity.

PASS CRITERIA: You can explain WHY multicollinearity breaks linear
regression using the words "rank," "invertible," and "pseudo-inverse."
```

---

### Week 7: Eigenvalues, Eigenvectors, and PCA

**Why this matters for ML:**
Remember V1-V28 in the credit card dataset? They're PCA features.
After this week, you'll understand what PCA did to the original data
and why it works.

```
WATCH (Layer 1):
├── 3Blue1Brown: "Eigenvectors and Eigenvalues" (Ch 14) — 17 min
│   → AN EIGENVECTOR is a direction that DOESN'T CHANGE when you apply
│     a transformation. It just gets scaled (stretched or squished).
│   → The EIGENVALUE is the scale factor.
│   → Covariance matrix eigenvectors = directions of maximum variance in data
│   → PCA = "find the eigenvectors of the covariance matrix and project
│     data onto them" = "find the directions where data varies most"
│
├── StatQuest: "PCA — Main Ideas" (5 min)
├── StatQuest: "PCA — Step by Step" (22 min)
│   → After this, V1-V28 will make sense:
│     V1 = projection onto the first principal component (most variance)
│     V2 = projection onto the second (next most variance)
│     etc.

PRACTICE (Layer 2):
├── Khan Academy: "Eigenvalues and eigenvectors"
│   → Focus on 2×2 examples. You don't need to compute 30×30 by hand.
│   → Goal: "I can explain what eigenvalues/eigenvectors ARE"
│
├── NOTATION DRILL:
│
│   Av = λv
│   → "When matrix A transforms vector v, v doesn't change direction,
│     it just gets scaled by λ"
│   → v = eigenvector, λ = eigenvalue
│
│   Cov(X) = (1/(n-1)) (X - X̄)ᵀ(X - X̄)
│   → Covariance matrix. Measures how features co-vary.
│   → IMPORTANT: X must be mean-centered first (subtract column means).
│     The shortcut (1/n)XᵀX only works if X is already mean-centered.
│   → We use (n-1) not n — Bessel's correction, same as std deviation.
│   → np.cov(X.T) computes this with (n-1) by default.
│   → If Cov(Amount, V14) is large: they move together
│   → PCA finds eigenvectors of this matrix
│
│   NOTE on (X - X̄)ᵀ:
│   → This uses the transpose from Week 5.
│   → X - X̄ is (n_samples × n_features)
│   → (X - X̄)ᵀ is (n_features × n_samples)
│   → (X - X̄)ᵀ(X - X̄) is (n_features × n_features) — a square matrix
│   → This square matrix CAN have eigenvalues. That's why the transpose is needed.

ML CONNECTION (Layer 3):
├── Apply PCA yourself:
│   from sklearn.decomposition import PCA
│   pca = PCA(n_components=2)
│   X_reduced = pca.fit_transform(X)
│   → pca.explained_variance_ratio_ tells you how much info each component keeps
│   → pca.components_ ARE the eigenvectors
│
└── NOW go back to the credit card dataset:
    → V1 captures the most variance, V2 the second most, etc.
    → V1-V28 together capture most of the original data's information
    → Amount and Time were kept as-is because they're interpretable
    → You finally understand what that dataset actually contains.
```

#### ✅ Week 7 Checkpoint Exercise

```
EIGENVALUE INTUITION:

Given matrix A = [[3, 1],
                  [0, 2]]

1)  Verify that v = [1, 0] is an eigenvector of A with eigenvalue 3:
    Compute A·v = ___
    Is the result = 3 × [1, 0]? ___

2)  Verify that v = [1, -1] is an eigenvector of A with eigenvalue 2:
    Compute A·v = ___
    Is the result = 2 × [1, -1]? ___

3)  In your own words, what does it MEAN geometrically that [1, 0]
    is an eigenvector with eigenvalue 3?
    Answer: ___

Verify in Python:
    import numpy as np
    A = np.array([[3,1],[0,2]])
    eigenvalues, eigenvectors = np.linalg.eig(A)
    print("Eigenvalues:", eigenvalues)
    print("Eigenvectors (columns):", eigenvectors)
    # Verify: A @ v should equal λ * v for each eigenpair

PCA REASONING:

4)  You run PCA on a dataset with 100 features. The first 3 components
    explain 85% of the variance. What does this tell you?
    Answer: ___

5)  If you keep only 3 components, you lose 15% of the information.
    When is this trade-off worth it? When isn't it?
    Answer: ___

--- ANSWERS ---

1)  A·[1,0] = [3×1+1×0, 0×1+2×0] = [3, 0] = 3 × [1, 0] ✓

2)  A·[1,-1] = [3×1+1×(-1), 0×1+2×(-1)] = [2, -2] = 2 × [1, -1] ✓

3)  When A transforms space, the direction [1, 0] (the x-axis) gets
    stretched by a factor of 3 but doesn't rotate. It's a "special"
    direction for this transformation.

4)  The data is highly redundant. 100 features, but the real
    "dimensionality" of the data is closer to 3. Most features
    are correlated and carry overlapping information.

5)  Worth it when: you need speed (fewer features = faster training),
    want to visualize high-dimensional data, or need to reduce
    multicollinearity.
    Not worth it when: that 15% contains the signal you care about
    (e.g., the difference between fraud and non-fraud might live
    in the smaller components).

PASS CRITERIA: You can explain PCA as "finding the eigenvectors of
the covariance matrix" and what that means for your data.
```

---

### Week 8: Embeddings, Similarity, and Norms

**Why this matters for ML:**
Word embeddings, sentence embeddings, transaction embeddings — the
modern ML stack runs on representing things as vectors and measuring
distances between them. RAG retrieval, nearest-neighbor search,
clustering — all vector similarity.

```
WATCH (Layer 1):
├── 3Blue1Brown: "Dot products" (Ch 7) — re-watch with new eyes
│   → Dot product measures SIMILARITY between vectors
│   → Cosine similarity = dot product of normalized vectors
│   → When you search a vector DB in RAG, this is the math
│
├── StatQuest: "Word Embeddings and Word2Vec" (12 min)
│   → Words become vectors. Similar words = close vectors.
│   → "king - man + woman ≈ queen" = vector arithmetic

PRACTICE (Layer 2):
├── NOTATION DRILL:
│
│   cos(θ) = (a · b) / (||a|| · ||b||)
│   → Cosine similarity. Ranges from -1 to 1.
│   → 1 = identical direction, 0 = perpendicular, -1 = opposite
│   → sklearn.metrics.pairwise.cosine_similarity does this
│
│   ||x|| = sqrt(Σ xᵢ²)
│   → L2 norm (Euclidean length). "How long is this vector?"
│   → np.linalg.norm(x) computes this
│
│   ||x||₁ = Σ |xᵢ|
│   → L1 norm (Manhattan distance). Sum of absolute values.
│   → This matters for regularization:
│     - L1 penalty (Lasso): λ·||w||₁ = λ·Σ|wᵢ| → pushes weights to exactly 0
│     - L2 penalty (Ridge): λ·||w||² = λ·Σwᵢ² → pushes weights toward 0
│     - L1 gives sparse models (feature selection)
│     - L2 gives small but non-zero weights (prevents extremes)
│
│   WHY L1 GIVES EXACT ZEROS (L2 DOESN'T):
│   The full picture has two parts:
│   (a) GRADIENT ARGUMENT: The gradient of |w| is ±1 regardless of how
│       small w is (constant push toward zero). The gradient of w² is 2w,
│       which shrinks as w → 0 (push gets weaker near zero). So L1 pushes
│       small weights to zero with constant force; L2's force fades out.
│   (b) GEOMETRY ARGUMENT (deeper): The L1 constraint region is a diamond
│       shape with sharp corners at the axes (where some weight = 0). The
│       L2 region is a smooth sphere. When the loss contours (ellipses)
│       intersect the constraint region, they're far more likely to hit a
│       corner of the diamond (weight exactly zero) than a point on the
│       smooth sphere surface. This is the real reason L1 gives sparsity.
│   Both explanations are correct. The gradient argument tells you "why do
│   small weights die?" The geometry argument tells you "why do they land
│   on exactly zero rather than just very small?"

ML CONNECTION (Layer 3):
├── Compute cosine similarity between fraud transactions:
│   → Are fraud transactions more similar to each other than to legit ones?
│   → from sklearn.metrics.pairwise import cosine_similarity
│   → This is the mathematical basis of anomaly detection:
│     anomalies are "far away" from normal points in vector space
│
└── If you use embeddings or RAG at work:
    → The retrieval step = "find the vectors with highest cosine similarity"
    → The embedding model = "convert text to a vector where meaning is preserved"
    → Now you know what "meaning is preserved" means mathematically:
      similar texts → vectors with high cosine similarity
```

#### ✅ Week 8 Checkpoint Exercise

```
SIMILARITY COMPUTATION:

Given three vectors:
  a = [1, 0, 1]
  b = [1, 1, 0]
  c = [2, 0, 2]

1)  Compute ||a||, ||b||, ||c||:
    ||a|| = sqrt(1² + 0² + 1²) = ___
    ||b|| = ___
    ||c|| = ___

2)  Compute cosine similarity between a and b:
    a · b = 1×1 + 0×1 + 1×0 = ___
    cos(a,b) = (a·b) / (||a|| × ||b||) = ___

3)  Compute cosine similarity between a and c:
    a · c = ___
    cos(a,c) = ___

4)  Explain: a and c point in the SAME direction but c is twice as
    long. What does cosine similarity say about them vs. a and b?
    Answer: ___

5)  When would you use cosine similarity vs. Euclidean distance?
    Answer: ___

REGULARIZATION:

6)  Given weights w = [3.0, 0.1, -2.0, 0.0, 5.0]:
    Compute L1 penalty: Σ|wᵢ| = ___
    Compute L2 penalty: Σwᵢ² = ___

7)  If you apply strong L1 regularization, which weights would
    likely go to zero first? Why? Give both the gradient and
    geometry explanations.
    Answer: ___

Verify in Python:
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    a, b, c = [1,0,1], [1,1,0], [2,0,2]
    print(cosine_similarity([a], [b]))  # should be 0.5
    print(cosine_similarity([a], [c]))  # should be 1.0

--- ANSWERS ---

1)  ||a|| = sqrt(2) ≈ 1.414
    ||b|| = sqrt(1+1+0) = sqrt(2) ≈ 1.414
    ||c|| = sqrt(4+0+4) = sqrt(8) ≈ 2.828

2)  a · b = 1
    cos(a,b) = 1 / (1.414 × 1.414) = 1/2 = 0.5

3)  a · c = 1×2 + 0×0 + 1×2 = 4
    cos(a,c) = 4 / (1.414 × 2.828) = 4/4 = 1.0

4)  cos(a,c) = 1.0 → perfect similarity. Cosine ignores magnitude,
    only cares about direction. a and c point the same way.
    cos(a,b) = 0.5 → partially similar. Different directions.
    This is why cosine similarity is used for embeddings: we care
    about MEANING (direction) not MAGNITUDE (length).

5)  Cosine: when direction matters more than magnitude (text similarity,
    embeddings, document comparison).
    Euclidean: when absolute position matters (geographic distance,
    anomaly detection based on "how far from normal").

6)  L1 = |3| + |0.1| + |-2| + |0| + |5| = 10.1
    L2 = 9 + 0.01 + 4 + 0 + 25 = 38.01

7)  The small weights (0.1) go to zero first.
    Gradient: L1's subgradient at any non-zero point is ±1 (constant
    force). Small weights like 0.1 are already near zero and get pushed
    across with constant force. L2's gradient is 2w = 0.2 (weak force
    for small weights) — never enough to push to exactly zero.
    Geometry: the L1 diamond constraint has corners on the axes.
    When the loss function's contours touch the diamond, they hit a
    corner (where a weight is exactly zero) more often than they hit
    the smooth surface of the L2 sphere.

PASS CRITERIA: You can compute cosine similarity by hand and explain
why L1 produces exact zeros while L2 doesn't, using both arguments.
```

---

### Week 9: Derivatives, Chain Rule, and Second Derivatives

**Why this matters for ML:**
Backpropagation, gradient descent, optimization — all calculus.
This week focuses ONLY on derivatives and the chain rule.
We split calculus across two weeks (this one + Week 10) because
rushing this is where most people stall out.

```
WATCH (Layer 1):
├── 3Blue1Brown: "Essence of Calculus" Ch 1-4
│   Ch 1: Derivatives — the geometry of change
│   Ch 2: Visualizing derivatives
│   Ch 3: Derivative formulas through geometry
│   Ch 4: Chain rule
│   → After these 4 videos, derivatives will feel visual, not symbolic.
│
│   KEY INSIGHT:
│   A derivative answers ONE question: "If I nudge the input a tiny
│   bit, how much does the output change?"
│   → df/dx = "the ratio of tiny change in f to tiny change in x"
│   → If f(x) = x², then df/dx = 2x
│   → At x=3: df/dx = 6, meaning "near x=3, every tiny nudge to x
│     causes f to change by about 6 times as much"

PRACTICE (Layer 2):
├── Khan Academy: "Derivatives: definition and basic rules"
│   → Focus on: power rule, chain rule, product rule
│   → 30 min/day. Spend a FULL WEEK on this.
│   → You need to READ derivatives fluently, even if you
│     don't solve complex ones.
│
├── CORE DERIVATIVE RULES (memorize these):
│
│   Power rule:      d/dx[xⁿ] = n·xⁿ⁻¹
│   Constant rule:   d/dx[c] = 0
│   Sum rule:        d/dx[f + g] = df/dx + dg/dx
│   Product rule:    d/dx[f·g] = f'g + fg'
│   Chain rule:      d/dx[f(g(x))] = f'(g(x)) · g'(x)
│
│   IMPORTANT DERIVATIVES FOR ML:
│   d/dx[eˣ] = eˣ         (exponential is its own derivative!)
│   d/dx[ln(x)] = 1/x     (shows up in log-likelihood)
│   d/dx[1/(1+e⁻ˣ)] = σ(x)·(1-σ(x))   (sigmoid derivative — elegant!)
│
├── SECOND DERIVATIVES:
│   The second derivative d²f/dx² is the derivative of the derivative.
│   → First derivative tells you the SLOPE (rate of change)
│   → Second derivative tells you the CURVATURE (how the slope changes)
│
│   d²f/dx² > 0 → function curves UPWARD (convex / bowl-shaped)
│   d²f/dx² < 0 → function curves DOWNWARD (concave / hill-shaped)
│   d²f/dx² = 0 → inflection point (changes from curving up to down)
│
│   EXAMPLE: f(x) = x²
│   f'(x) = 2x      (slope increases as x increases)
│   f''(x) = 2       (constant positive curvature → always convex)
│   → This is why MSE loss is convex: it's a sum of x² terms.
│
│   WHY THIS MATTERS:
│   → XGBoost uses second derivatives (Hessian) to build trees.
│     The XGBoost paper's Section 2.2 uses a second-order Taylor
│     expansion: L(y + Δ) ≈ L(y) + L'(y)·Δ + ½L''(y)·Δ²
│     First derivative (gradient) = direction to move.
│     Second derivative (Hessian) = how far to step.
│     Using both → faster convergence than gradient-only methods.
│   → You'll see this in the paper reading exercise in Week 14.
│
├── CHAIN RULE IN DEPTH:
│   The chain rule is the MOST IMPORTANT calculus concept for ML.
│   It says: if y = f(g(x)), then dy/dx = (dy/dg) · (dg/dx)
│
│   EXAMPLE — sigmoid of a linear function:
│   y = sigmoid(wx + b) = 1/(1 + e^(-(wx+b)))
│
│   To find dy/dw, trace the chain:
│     Let z = wx + b        (linear combination)
│     Let y = sigmoid(z)    (activation)
│     dy/dw = dy/dz · dz/dw
│           = sigmoid(z)·(1-sigmoid(z)) · x
│
│   This IS what happens in one step of logistic regression training.
│   The chain rule lets you compute "how does changing w affect the
│   final prediction?" through a chain of intermediate steps.

ML CONNECTION (Layer 3):
└── Compute the derivative of MSE loss with respect to w:
    → Loss = (1/n)Σ(wx + b - y)²
    → dL/dw = (2/n)Σ x·(wx + b - y)
    → This is the gradient that gradient descent uses to update w.
    → Don't just read this — derive it yourself using the chain rule:
      Let e = wx + b - y  (error)
      L = (1/n)Σ e²
      dL/de = 2e/n
      de/dw = x
      dL/dw = dL/de · de/dw = (2/n)·e·x = (2/n)·x·(wx + b - y)

    And the second derivative:
      d²L/dw² = (2/n)Σ x²
    → This is always positive (x² ≥ 0) → MSE is convex in w.
    → Gradient descent ALWAYS finds the global minimum for MSE.
```

#### ✅ Week 9 Checkpoint Exercise

```
DERIVATIVE COMPUTATION:

1)  d/dx[3x⁴ + 2x² - 7x + 5] = ___

2)  d/dx[e²ˣ] = ___
    Hint: chain rule with g(x) = 2x

3)  d/dx[ln(3x)] = ___
    Hint: chain rule with g(x) = 3x

4)  d/dx[(2x + 1)³] = ___
    Hint: chain rule with g(x) = 2x + 1

SECOND DERIVATIVES:

5)  f(x) = x³ - 3x
    f'(x) = ___
    f''(x) = ___
    At x=1: is f convex or concave? ___
    At x=-1: is f convex or concave? ___

CHAIN RULE FOR ML:

6)  Given y = sigmoid(z) where z = 3x + 2:
    Compute dy/dx.
    Step 1: dy/dz = sigmoid(z) · (1 - sigmoid(z))
    Step 2: dz/dx = ___
    Step 3: dy/dx = dy/dz · dz/dx = ___

7)  Given Loss = (ŷ - y)² where ŷ = wx + b:
    Compute dLoss/dw.
    Step 1: dLoss/dŷ = ___
    Step 2: dŷ/dw = ___
    Step 3: dLoss/dw = ___

8)  In plain English: what does dLoss/dw TELL you?
    What does d²Loss/dw² tell you?
    Answer: ___

--- ANSWERS ---

1)  12x³ + 4x - 7

2)  e²ˣ · 2 = 2e²ˣ

3)  (1/(3x)) · 3 = 1/x

4)  3(2x+1)² · 2 = 6(2x+1)²

5)  f'(x) = 3x² - 3
    f''(x) = 6x
    At x=1: f''(1) = 6 > 0 → convex (curving upward)
    At x=-1: f''(-1) = -6 < 0 → concave (curving downward)

6)  Step 2: dz/dx = 3
    Step 3: dy/dx = 3 · sigmoid(z) · (1 - sigmoid(z))
    where z = 3x + 2

7)  Step 1: dLoss/dŷ = 2(ŷ - y)
    Step 2: dŷ/dw = x
    Step 3: dLoss/dw = 2(ŷ - y) · x = 2x(wx + b - y)

8)  dLoss/dw: "How much does the loss change if I increase w by a
    tiny amount?" Tells you the DIRECTION to update w.
    d²Loss/dw²: "How fast is the gradient itself changing?" Tells you
    the CURVATURE — whether you should take a big step (flat curvature)
    or a small one (steep curvature). XGBoost uses this to set step sizes.

PASS CRITERIA: You can apply the chain rule through a 2-step
composition, compute a second derivative, and explain what both
first and second derivatives mean for model training.
```

---

### Week 10: Gradients, Gradient Descent, and Backpropagation

**Why this matters for ML:**
This week ties everything together. Matrices (Week 5-6) + derivatives
(Week 9) = backpropagation. This is how every neural network, every
deep learning model, and every gradient-boosted tree actually learns.

**We also introduce convexity here — the natural place, since it
directly answers "when does gradient descent work perfectly?"**

```
WATCH (Layer 1):
├── 3Blue1Brown: "Neural Networks" series (4 videos)
│   → Ch 1: What is a neural network?
│   → Ch 2: Gradient descent
│   → Ch 3: Backpropagation
│   → Ch 4: Backpropagation calculus
│   → This ties EVERYTHING together: matrices, derivatives, chain rule

PRACTICE (Layer 2):
├── NOTATION DRILL:
│
│   ∂L/∂w
│   → "Partial derivative of loss with respect to weight w"
│   → "How much does loss change if I nudge THIS weight a tiny bit,
│     holding all other weights fixed?"
│   → The ∂ (vs d) means we're differentiating with respect to ONE
│     variable while treating others as constants.
│   → This is THE core computation in all neural network training.
│
│   w_new = w_old - α · ∂L/∂w
│   → Gradient descent update rule. α = learning rate.
│   → "Move the weight in the direction that REDUCES loss"
│   → "How far to move" = learning rate × gradient
│   → learning_rate=0.1 in XGBoost: this α.
│
│   ∂L/∂w₁ = ∂L/∂ŷ · ∂ŷ/∂z · ∂z/∂w₁
│   → Chain rule for multiple layers. This IS backpropagation.
│   → "To know how w₁ affects the loss, trace the chain of effects:
│     w₁ affects z (the weighted sum),
│     z affects ŷ (through activation function),
│     ŷ affects L (through loss function)"
│
│   ∇L = [∂L/∂w₁, ∂L/∂w₂, ..., ∂L/∂wₙ]
│   → Gradient vector. The collection of ALL partial derivatives.
│   → Points in the direction of steepest INCREASE in loss.
│   → We go in the OPPOSITE direction (gradient descent = walk downhill).
│
│   CONVEXITY:
│   A function is CONVEX if any line segment between two points on
│   the curve lies above the curve. Think "bowl-shaped."
│
│   → CONVEX loss surfaces: ONE global minimum. Gradient descent
│     ALWAYS finds it (with appropriate learning rate).
│     - Linear regression (MSE): convex (d²L/dw² = (2/n)Σxᵢ² > 0, from Week 9)
│     - Logistic regression (log loss): convex
│     - SVM (hinge loss): convex
│     → model.fit() gives you the global optimum. Done.
│
│   → NON-CONVEX loss surfaces: MANY local minima, saddle points.
│     Gradient descent might get stuck.
│     - Neural networks: non-convex
│     → This is why: initialization matters, learning rate schedules
│       help, Adam outperforms vanilla SGD, training the same
│       architecture twice gives different results.
│
│   → This explains a practical mystery: why does logistic regression
│     give the SAME answer every time you run it, but a neural network
│     doesn't? Convexity (one minimum) vs non-convexity (many minima).

ML CONNECTION (Layer 3):
└── Manual gradient descent on linear regression:
    → y = wx + b, Loss = MSE = (1/n)Σ(wx + b - y)²
    → ∂L/∂w = (2/n)Σx(wx + b - y)
    → ∂L/∂b = (2/n)Σ(wx + b - y)
    → Start with w=0, b=0. Compute gradients. Update. Repeat 50 times.
    → Plot the loss curve. Watch w and b converge toward sklearn's solution.
    → This exercise takes ~30 lines of numpy. It will cement gradient descent
      in your mind permanently.
```

#### ✅ Week 10 Checkpoint Exercise

```
GRADIENT DESCENT BY HAND — 1D:

Simple 1D example: Loss = (w - 3)²
(The minimum is obviously at w = 3. Let's watch GD find it.)

dL/dw = 2(w - 3)

Starting at w = 0, learning rate α = 0.1:

Step 0: w = 0.0
  gradient = 2(0 - 3) = -6.0
  w_new = 0.0 - 0.1 × (-6.0) = 0.6
  Loss = (0.6 - 3)² = 5.76

Step 1: w = 0.6
  gradient = 2(0.6 - 3) = ___
  w_new = 0.6 - 0.1 × (___) = ___
  Loss = ___

Step 2: w = ___
  gradient = ___
  w_new = ___
  Loss = ___

1)  Complete steps 1 and 2.

2)  Is the loss decreasing each step? Is w approaching 3?

3)  What happens if α = 2.0? (Compute step 0 and step 1.)

4)  What happens if α = 0.001? (Compute step 0.)

GRADIENT DESCENT — 2D (this is important — real ML is always multi-dimensional):

Loss = (w₁ - 2)² + (w₂ - 5)²

5)  Compute the gradient: ∇L = [∂L/∂w₁, ∂L/∂w₂] = ___

6)  Starting at (w₁, w₂) = (0, 0), α = 0.1:
    gradient = [2(0-2), 2(0-5)] = ___
    (w₁_new, w₂_new) = (0, 0) - 0.1 × ___ = ___
    Both parameters updated SIMULTANEOUSLY in one step.

7)  Why is this 2D example important?
    Answer: ___

--- ANSWERS ---

1)  Step 1: gradient = 2(0.6-3) = -4.8
    w_new = 0.6 - 0.1×(-4.8) = 1.08
    Loss = (1.08-3)² = 3.6864

    Step 2: gradient = 2(1.08-3) = -3.84
    w_new = 1.08 - 0.1×(-3.84) = 1.464
    Loss = (1.464-3)² = 2.362

2)  Yes. Loss: 5.76 → 3.69 → 2.36 (decreasing).
    w: 0 → 0.6 → 1.08 → 1.464 (approaching 3).

3)  α = 2.0:
    Step 0: w_new = 0 - 2.0×(-6.0) = 12.0  (overshot past 3!)
    Step 1: w=12, gradient = 2(12-3) = 18.0
    w_new = 12 - 2.0×18.0 = -24.0  (even further away!)
    DIVERGENCE. Learning rate too high → oscillating and exploding.

4)  α = 0.001:
    w_new = 0 - 0.001×(-6.0) = 0.006. After one step, barely moved.
    Would need thousands of steps to reach 3. Too slow.

5)  ∇L = [2(w₁ - 2), 2(w₂ - 5)]

6)  gradient = [-4, -10]
    (w₁_new, w₂_new) = (0, 0) - 0.1×[-4, -10] = (0.4, 1.0)
    Both parameters move toward their targets (2 and 5) simultaneously.

7)  In real ML, you always have multiple weights (often millions).
    The gradient ∇L is a VECTOR that simultaneously tells you the
    direction to move ALL parameters at once. This is the power of
    the gradient — it's not separate 1D problems, it's one coordinated
    step in high-dimensional space.

PASS CRITERIA: You can trace through gradient descent steps in both
1D and 2D, and predict the effect of changing the learning rate.
```

---

## 🏁 PHASE 2 GATE — Complete Before Moving On

```
Before starting Phase 3, verify you can do ALL of the following
WITHOUT looking at notes:

[ ] Multiply a 2×2 matrix by a vector by hand
[ ] Compute a transpose and explain why Xᵀ appears in the normal equation
[ ] Explain what rank means and why multicollinearity breaks linear regression
[ ] Explain eigenvalues/eigenvectors and how PCA uses them
[ ] Compute cosine similarity between two vectors
[ ] Explain why L1 gives sparsity but L2 doesn't (both gradient and geometry reasons)
[ ] Apply the chain rule through a 2-step composition
[ ] Compute a second derivative and explain what it means (curvature)
[ ] Explain partial derivatives vs. regular derivatives
[ ] Trace through gradient descent with 2 parameters simultaneously
[ ] Explain convexity and why logistic regression always converges but NNs don't

If you can't pass 9/11, spend an extra week on the weak areas.
Phase 3 builds directly on every one of these concepts.
```

---

## PHASE 3: APPLIED ML MATH (Weeks 11–14)
### Connect everything to the algorithms you use daily

---

### Week 11: Decision Trees and Ensemble Math

**Why this matters:**
XGBoost, Random Forest, LightGBM — these dominate tabular ML.
Understanding the math means you can tune them with reasoning
instead of guessing hyperparameters.

```
WATCH:
├── StatQuest: "Decision Trees" (18 min)
├── StatQuest: "Random Forests" (10 min)
├── StatQuest: "XGBoost" series (4 videos, ~40 min total)
│   → These are THE definitive visual explanations

KEY CONCEPTS:
├── GINI IMPURITY — how decision trees choose where to split
│   Gini = 1 - Σ pᵢ²
│   → pᵢ = proportion of class i in a node
│   → Pure node (all one class): Gini = 0
│   → Worst case (50/50): Gini = 0.5
│   → Tree picks the split that REDUCES Gini the most
│
├── INFORMATION GAIN — alternative split criterion
│   Entropy = -Σ pᵢ · log₂(pᵢ)
│   → Same idea as Gini: measures "disorder" in a node
│   → criterion='entropy' vs criterion='gini' in sklearn
│   → Usually doesn't matter much. Now you know what they mean.
│
├── GRADIENT BOOSTING — what XGBoost actually does
│   1. Start with a simple prediction (e.g., log-odds of fraud)
│   2. Compute the NEGATIVE GRADIENT of the loss function
│   3. Train a new tree to predict these "pseudo-residuals"
│   4. Add the new tree's predictions (scaled by learning_rate)
│   5. Repeat from step 2.
│
│   CRITICAL DISTINCTION — "residuals" vs "pseudo-residuals":
│   → For MSE loss, the negative gradient = yᵢ - ŷᵢ. These ARE the
│     classical residuals. So "fit to the residuals" is literally correct.
│   → For LOG LOSS (your fraud detection use case), the negative gradient
│     = yᵢ - pᵢ, where pᵢ = sigmoid(ŷᵢ). These are NOT the classical
│     residuals (which would be yᵢ - ŷᵢ on the log-odds scale). They're
│     called "pseudo-residuals" because they play the same role — they
│     tell the next tree "where and by how much the current ensemble is
│     wrong" — but they come from the gradient of a different loss.
│   → The word "gradient" in gradient boosting = this. Each tree fits
│     the negative gradient of whatever loss function you chose.
│
│   → n_estimators = number of trees (steps)
│   → max_depth = complexity of each tree
│   → learning_rate = how much to trust each new tree (α from Week 10!)
│
│   XGBoost's SECOND-ORDER TWIST:
│   → Standard gradient boosting uses only the first derivative (gradient).
│   → XGBoost also uses the second derivative (Hessian, from Week 9).
│   → It approximates the loss with a second-order Taylor expansion:
│     L(y + Δ) ≈ L(y) + g·Δ + ½h·Δ²
│     where g = ∂L/∂ŷ (gradient) and h = ∂²L/∂ŷ² (Hessian)
│   → This gives the optimal leaf weight as: w* = -g/h
│     (vs just w* = -g in standard gradient boosting)
│   → Using curvature information → faster convergence → fewer trees needed.
│   → You'll see this in the XGBoost paper in Week 14.
│
└── REGULARIZATION in XGBoost
    → reg_alpha = L1 (lasso): λ₁·Σ|wᵢ| → pushes leaf weights to exactly 0
    → reg_lambda = L2 (ridge): λ₂·Σwᵢ² → pushes leaf weights toward 0
    → min_child_weight = minimum sum of Hessians (h) in a leaf
      → For log loss: h = p(1-p), so min_child_weight controls the
        minimum amount of "statistical confidence" needed per leaf.
      → Near-certain predictions (p≈0 or p≈1) have small h → they need
        more samples to meet the threshold → prevents overfitting on
        easy cases.
    → NOW you understand WHY these hyperparameters exist:
      reg_alpha/reg_lambda → norm penalties from Week 8
      learning_rate → gradient descent step size from Week 10
      max_depth → bias-variance tradeoff (see Week 12)

PRACTICE:
└── Re-tune your XGBoost fraud model, but this time you KNOW what each
    parameter does mathematically. Explain your choices in writing:
    "I set max_depth=6 because deeper trees risk overfitting on 0.17%
     fraud class. I set learning_rate=0.05 with n_estimators=300 because
     smaller steps with more iterations gives smoother convergence
     (same principle as Week 10: low α, more steps)."
```

#### ✅ Week 11 Checkpoint Exercise

```
GINI IMPURITY BY HAND:

A decision tree node contains 100 samples: 70 legit, 30 fraud.

1)  Compute Gini impurity:
    Gini = 1 - (p_legit² + p_fraud²)
         = 1 - ((70/100)² + (30/100)²)
         = ___

Now it considers a split:
  Left child:  60 legit, 5 fraud   (65 total)
  Right child: 10 legit, 25 fraud  (35 total)

2)  Compute Gini for each child:
    Gini_left  = 1 - ((60/65)² + (5/65)²)  = ___
    Gini_right = 1 - ((10/35)² + (25/35)²) = ___

3)  Compute weighted average Gini after split:
    Gini_split = (65/100) × Gini_left + (35/100) × Gini_right = ___

4)  Is this split better than no split? By how much?
    Gini reduction = Gini_parent - Gini_split = ___

5)  Alternative split:
    Left:  35 legit, 15 fraud  (50 total)
    Right: 35 legit, 15 fraud  (50 total)
    Gini_left = Gini_right = 1 - ((35/50)² + (15/50)²) = ___
    Is this split useful? Why or why not?

GRADIENT BOOSTING REASONING:

6)  For binary classification with log loss, the pseudo-residual for
    sample i is (yᵢ - pᵢ). If yᵢ = 1 (fraud) and current prediction
    pᵢ = 0.2, the pseudo-residual is ___.
    What does this tell the next tree?

7)  Why does XGBoost typically need fewer trees than standard gradient
    boosting for the same performance? (Hint: second derivatives.)

--- ANSWERS ---

1)  Gini = 1 - (0.49 + 0.09) = 0.42

2)  Gini_left  = 1 - ((60/65)² + (5/65)²)
               = 1 - (0.8521 + 0.0059) = 1 - 0.8580 = 0.142
    Gini_right = 1 - ((10/35)² + (25/35)²)
               = 1 - (0.0816 + 0.5102) = 1 - 0.5918 = 0.408

3)  Gini_split = 0.65 × 0.142 + 0.35 × 0.408
               = 0.092 + 0.143 = 0.235

4)  Gini reduction = 0.42 - 0.235 = 0.185 → good split!

5)  Gini = 1 - (0.49 + 0.09) = 0.42
    Same as the parent. This split is useless — it doesn't
    separate the classes at all.

6)  Pseudo-residual = 1 - 0.2 = 0.8.
    This tells the next tree: "for this sample, the current ensemble
    is under-predicting by 0.8. Push the prediction higher."

7)  XGBoost uses both gradient (direction) AND Hessian (curvature)
    to determine optimal leaf weights. Standard boosting uses only
    the gradient. Having curvature info means XGBoost can take better-
    sized steps — not too big (overshoot) or too small (waste iterations).
    Analogous to Newton's method vs basic gradient descent in Week 10.

PASS CRITERIA: You can compute Gini impurity, explain why a split is
good or bad, and explain pseudo-residuals for log loss.
```

---

### Week 12: Loss Functions, Information Theory, and Bias-Variance

**Why this matters:**
Every model training is loss minimization. Understanding loss functions
means you can choose the right one, debug when training goes wrong,
and build custom losses. The bias-variance tradeoff is the mathematical
backbone of every regularization and ensemble decision.

```
WATCH:
├── StatQuest: "Entropy" (12 min)
├── StatQuest: "Cross-Entropy" (7 min)
├── StatQuest: "KL Divergence" (7 min)
├── StatQuest: "Bias and Variance" (7 min)

KEY CONCEPTS:
├── ENTROPY — "how surprised should I be on average?"
│   H(p) = -Σ p(x) · log p(x)
│   → High entropy = lots of surprise = high uncertainty
│   → Low entropy = predictable = low uncertainty
│   → Uniform distribution = maximum entropy
│
├── CROSS-ENTROPY LOSS — THE fraud detection loss function
│   L = -[y·log(p) + (1-y)·log(1-p)]
│   → If y=1 (fraud) and p=0.01 (model says 1% fraud):
│     L = -log(0.01) = 4.6 → HIGH loss, model is very wrong
│   → If y=1 and p=0.99: L = -log(0.99) = 0.01 → LOW loss, model is right
│   → The -log shape punishes confident wrong predictions SEVERELY
│
├── FOCAL LOSS — for extreme class imbalance
│   FL(pₜ) = -αₜ(1-pₜ)^γ · log(pₜ)
│   → Where pₜ = p if y=1, and pₜ = (1-p) if y=0
│   → αₜ = class weight (α for y=1, 1-α for y=0)
│   → (1-pₜ)^γ = modulating factor: easy examples get downweighted
│   → When γ=0: focal loss = standard cross-entropy (weighted by αₜ)
│   → When γ=2: confident correct predictions contribute almost zero loss
│   → Forces the model to focus on hard, misclassified examples
│
├── KL DIVERGENCE
│   D_KL(P||Q) = Σ P(x) · log(P(x)/Q(x))
│   → "How different are distributions P and Q?"
│   → Cross-entropy = entropy + KL divergence: H(P,Q) = H(P) + D_KL(P||Q)
│   → Used in: VAE training, knowledge distillation, model compression
│
└── BIAS-VARIANCE TRADEOFF
    For squared error loss, the expected prediction error decomposes cleanly:

    E[(y - ŷ)²] = Bias(ŷ)² + Var(ŷ) + σ²_noise

    where expectations are over different possible training sets.

    BIAS(ŷ) = E[ŷ] - f(x)
    → How far off the model's AVERAGE prediction is from the true function
    → High bias: model is too simple, misses the pattern (underfitting)
    → Example: linear regression on a clearly nonlinear relationship

    Var(ŷ) = E[(ŷ - E[ŷ])²]
    → How much predictions CHANGE across different training sets
    → High variance: model is too complex, fits noise (overfitting)
    → Example: very deep decision tree memorizes training data

    σ²_noise = IRREDUCIBLE NOISE = randomness in the data itself
    → You can't reduce this. It's the floor.

    THE TRADEOFF:
    → More complexity → less bias, more variance
    → Less complexity → more bias, less variance
    → Sweet spot: minimize total error (bias² + variance)

    ⚠ IMPORTANT CAVEAT: This clean decomposition is derived under
    squared error (MSE). For classification with log loss (your fraud
    detection use case), a bias-variance decomposition exists but takes
    a different form (see Domingos, 2000). The INTUITION transfers
    perfectly — simpler models underfit, complex models overfit, there's
    a sweet spot — even though the exact algebra is different.

    HOW THIS MAPS TO HYPERPARAMETERS:
    → max_depth ↑: less bias, more variance
    → reg_lambda ↑: more bias, less variance
    → n_estimators ↑ (with low learning_rate): reduces bias without much
      variance increase (this is WHY boosting works)
    → Random Forest averages many high-variance trees → reduces variance
      while keeping bias low (this is WHY bagging works)

PRACTICE:
├── Compute cross-entropy loss for 5 predictions (from Week 3,
│   but now you understand WHY -log has this shape)
│
└── For each hyperparameter in XGBoost, classify it as primarily
    affecting bias or variance. Then explain WHY using the math.
```

#### ✅ Week 12 Checkpoint Exercise

```
BIAS-VARIANCE REASONING:

1)  You train a decision tree with max_depth=1 (a "stump") on
    fraud data. It achieves 60% recall on training and 59% on test.
    Diagnosis: high ___ or high ___?
    What should you do?

2)  You train a decision tree with max_depth=50. It achieves
    99.9% recall on training but 65% on test.
    Diagnosis: high ___ or high ___?
    What should you do?

3)  You train a Random Forest with 500 trees, max_depth=50.
    It achieves 95% recall on training and 88% on test.
    The gap is smaller than #2. Why does Random Forest help?

4)  Explain in ONE sentence why boosting (XGBoost) works,
    using the terms "bias" and "variance."

LOSS FUNCTION SELECTION:

5)  Your model predicts [0.6, 0.55, 0.51] for three true fraud cases.
    These are all "correct" (>0.5) but not confident.
    Compute cross-entropy for each: -log(0.6), -log(0.55), -log(0.51)
    ≈ ___, ___, ___

6)  Now compute focal loss with γ=2, αₜ=1 (setting class weight to 1
    for simplicity, to isolate the effect of the modulating factor):
    -(1-p)² · log(p)
    -(0.4)² · log(0.6), -(0.45)² · log(0.55), -(0.49)² · log(0.51)
    ≈ ___, ___, ___

7)  Compare the two. What does focal loss do differently?

--- ANSWERS ---

1)  High BIAS (underfitting). Training and test scores are both low.
    The model is too simple to capture the fraud pattern.
    Fix: increase complexity (deeper trees, more features, ensemble).

2)  High VARIANCE (overfitting). Training score is near-perfect but
    test score is much lower. The model memorized training data.
    Fix: reduce complexity (limit depth, add regularization, prune).

3)  Random Forest averages many high-variance trees. Each tree
    overfits differently (due to bootstrap sampling + feature
    subsampling). Averaging cancels out the individual noise.
    Variance ↓ while bias stays approximately the same.

4)  Boosting sequentially reduces bias by having each new tree
    correct the errors (pseudo-residuals) of the ensemble so far,
    while the low learning rate and regularization control variance.

5)  -log(0.6) ≈ 0.511, -log(0.55) ≈ 0.598, -log(0.51) ≈ 0.673

6)  With αₜ=1 (to isolate the modulating effect):
    -(0.4)²(0.511) ≈ 0.082, -(0.45)²(0.598) ≈ 0.121,
    -(0.49)²(0.673) ≈ 0.162

7)  Focal loss dramatically reduced the loss for all three. But
    more importantly, it reduced the loss for the most confident
    prediction (0.6) by ~84% while reducing the uncertain one
    (0.51) by ~76%. Focal loss says "stop worrying about examples
    you already classify correctly and focus on the hard cases."
    In practice, αₜ would also differ between classes to weight
    fraud samples more heavily than legit ones.

PASS CRITERIA: You can diagnose bias vs. variance from training/test
gaps and explain which hyperparameters to adjust and why.
```

---

### Week 13: Optimization Deep Dive — SGD, Adam, and Numerical Stability

**Why this matters:**
"The model isn't converging." "Training loss is oscillating."
"The model is stuck." — you hear these at work.
After this week, you'll know exactly what they mean and what to do.

```
WATCH:
├── StatQuest: "Stochastic Gradient Descent" (8 min)
├── StatQuest: "Adam Optimizer" (12 min) — the most common optimizer
├── (Optional) Distill.pub: "Why Momentum Really Works" — excellent visual

KEY CONCEPTS:
├── STOCHASTIC vs BATCH vs MINI-BATCH:
│   → Batch: compute gradient on ALL data, then update. Stable but slow.
│   → Stochastic (SGD): gradient on ONE sample, update. Noisy but fast.
│   → Mini-batch: gradient on a BATCH (e.g., 32). Best of both.
│   → batch_size in deep learning = this
│   → XGBoost's subsample parameter is analogous (fraction of data per tree)
│
├── MOMENTUM:
│   v_t = β·v_{t-1} + ∇L(θ_t)
│   θ_{t+1} = θ_t - α·v_t
│   → "Keep moving in the direction you've been going"
│   → Like a ball rolling downhill — it builds up speed
│   → Helps escape shallow local minima and speeds up convergence
│
├── ADAM OPTIMIZER:
│   → Combines momentum with adaptive learning rates (different
│     learning rate per parameter, based on past gradient magnitudes)
│   → Almost always the default for deep learning. Now you know why.
│   → Key insight: parameters with consistently large gradients get
│     smaller effective learning rates (to prevent oscillation),
│     while parameters with small gradients get larger rates
│     (to speed up their convergence).
│
├── LEARNING RATE SCHEDULING:
│   → Start high (explore broadly), decrease over time (fine-tune)
│   → Common schedules: step decay, cosine annealing, warm-up + decay
│   → In XGBoost: learning_rate is fixed, but the residuals naturally
│     shrink → each new tree makes smaller corrections → built-in schedule
│
├── EARLY STOPPING:
│   → "Converged" = loss stopped decreasing meaningfully
│   → Stop training when VALIDATION loss starts INCREASING
│     (model is overfitting — memorizing training data)
│   → early_stopping_rounds in XGBoost does exactly this
│   → This IS a regularization technique (limits model complexity
│     by limiting training time)
│
└── NUMERICAL STABILITY — three practical issues every ML practitioner hits:

    1) log(0) = -infinity. Breaks your code.
       → Fix: log(p + ε) where ε = 1e-15
       → sklearn does this internally. Now you know why.
       → We mentioned this briefly in Week 3. Here's the full picture.

    2) exp(1000) = infinity. Breaks softmax.
       → softmax(z) = exp(z) / Σexp(z)
       → If any zᵢ is large, exp(zᵢ) overflows to inf.
       → Fix: subtract max(z) first: softmax(z - max(z))
       → PROOF this is identical:
         softmax(z - c)ᵢ = exp(zᵢ - c) / Σexp(zⱼ - c)
                         = exp(zᵢ)·exp(-c) / Σexp(zⱼ)·exp(-c)
                         = exp(zᵢ) / Σexp(zⱼ) = softmax(z)ᵢ
         The exp(-c) cancels in numerator and denominator.
       → scipy.special.softmax does this automatically.

    3) Products of tiny probabilities underflow to 0.0 in float64.
       → Likelihood = Πᵢ P(xᵢ|θ). With 10,000 samples, each P < 1,
         the product → 0.0 exactly in floating point.
       → Fix: use LOG-likelihood: Σᵢ log P(xᵢ|θ). Sums stay finite.
       → This is why every implementation uses log-loss, not loss.
       → We covered this in Week 3. It keeps coming up because it's
         fundamental — numerical stability isn't a one-time topic,
         it's a mindset.

PRACTICE:
└── Implement gradient descent for linear regression from scratch:
    → 20-30 lines of numpy
    → Plot the loss curve over 100 iterations
    → Try learning_rate = 0.001, 0.01, 0.1, 1.0
    → Watch: 0.001 converges slowly, 0.1 converges fast, 1.0 diverges
    → Then add momentum (β=0.9) and see how it changes the curve
```

#### ✅ Week 13 Checkpoint Exercise

```
DIAGNOSING TRAINING PROBLEMS:

For each scenario, identify the problem and suggest a fix:

1)  Training loss decreases very slowly. After 1000 epochs it's
    still far from converging.
    Problem: ___
    Fix: ___

2)  Training loss oscillates wildly: 2.3, 0.8, 5.1, 0.3, 7.2...
    Problem: ___
    Fix: ___

3)  Training loss decreases steadily and plateaus at 0.02.
    Validation loss decreases to 0.15 then starts increasing.
    Problem: ___
    Fix: ___

4)  Training loss immediately returns NaN on the first epoch.
    Problem: ___
    Fix: ___

5)  You switch from logistic regression to a neural network on the
    same data. Logistic regression gives the same result every time
    you run it. The neural net gives different results each time.
    Explain why, using the word "convex." (From Week 10.)

NUMERICAL STABILITY:

6)  Compute softmax([1000, 1001, 1002]) naively:
    exp(1000) = ___. What's the problem?

7)  Apply the stability trick: subtract max (1002):
    softmax([-2, -1, 0])
    = [exp(-2), exp(-1), exp(0)] / (exp(-2) + exp(-1) + exp(0))
    Compute: = [___, ___, ___] / ___
             = [___, ___, ___]

    Verify in Python:
    import numpy as np
    from scipy.special import softmax
    print(softmax([1000, 1001, 1002]))  # works correctly
    # Compare: np.exp([1000,1001,1002]) / np.sum(np.exp([1000,1001,1002]))  # inf/inf = nan

--- ANSWERS ---

1)  Learning rate too low.
    Fix: increase learning rate or use Adam (adaptive rates).

2)  Learning rate too high. Overshooting the minimum each step.
    Fix: decrease learning rate.

3)  Overfitting. Training keeps improving but validation gets worse.
    Fix: early stopping, increase regularization, add dropout, or
    reduce model complexity.

4)  Numerical overflow/underflow. Likely exp() or log(0) somewhere.
    Fix: check for NaN-producing operations. Use numerically stable
    implementations (log(x + ε), softmax with max subtraction).

5)  Logistic regression has a convex loss surface — one global minimum,
    gradient descent always finds it regardless of initialization.
    Neural networks have non-convex loss surfaces — many local minima,
    different random initializations lead to different solutions.

6)  exp(1000) ≈ 1.97 × 10⁴³⁴. Overflows to inf in float64
    (max float64 ≈ 1.8 × 10³⁰⁸). Division becomes inf/inf = NaN.

7)  exp(-2) ≈ 0.135, exp(-1) ≈ 0.368, exp(0) = 1.0
    Sum = 1.503
    softmax = [0.090, 0.245, 0.665]
    Mathematically identical to softmax([1000, 1001, 1002]) but computable.

PASS CRITERIA: You can diagnose common training failures from loss
curve behavior and explain the softmax stability trick with proof.
```

---

### Week 14: Autoencoders, Anomaly Detection, and Reading a Paper

**Why this matters:**
Ties together everything for your financial crime focus.
Autoencoders for anomaly detection use dimensionality reduction
(PCA concepts from Week 7), reconstruction error (norms from Week 8),
and gradient-based training (Weeks 9-10).

**Note: Attention mechanisms / transformers have been moved to a
"What's Next" appendix. They require a depth of matrix calculus
that 14 weeks doesn't deliver, and they're not directly relevant
to your tabular fraud detection work right now.**

```
KEY CONCEPTS:
├── AUTOENCODERS (unsupervised anomaly detection)
│   → Encoder: X → z (compress data to smaller representation)
│   → Decoder: z → X' (reconstruct from compressed version)
│   → Loss = ||X - X'||² (reconstruction error — L2 norm from Week 8)
│   → Train on NORMAL transactions only
│   → Fraudulent transactions can't be reconstructed well → high error → anomaly
│   → The bottleneck z is DIMENSIONALITY REDUCTION — similar to PCA
│     but nonlinear (neural network vs linear transformation)
│   → Connection to PCA: with linear activations and one hidden layer,
│     an autoencoder LEARNS the same subspace as PCA
│
├── ISOLATION FOREST — tree-based anomaly detection
│   → Builds random trees. Anomalies are ISOLATED quickly (short path
│     from root to leaf). Normal points take longer to isolate.
│   → anomaly_score ∝ 1 / average_path_length
│   → Uses the same tree-splitting concepts from Week 11
│   → sklearn.ensemble.IsolationForest
│
├── SOFTMAX — turns any vector of numbers into probabilities
│   softmax(zᵢ) = e^zᵢ / Σ e^zⱼ
│   → Input: any real numbers (positive, negative, any magnitude)
│   → Output: probabilities that sum to 1
│   → Used in: multi-class classification, attention weights, LLM next-token prediction
│   → Remember the stability trick from Week 13: subtract max first!
│
└── ANOMALY THRESHOLDING — statistics come back (with a correction)
    → Train autoencoder on normal data → get reconstruction errors
    → These errors form a distribution. DO NOT blindly assume it's normal.
      Reconstruction errors are bounded below by zero and are typically
      right-skewed. The "3σ rule" from the normal distribution does NOT
      apply here.
    → CORRECT APPROACH: examine the empirical distribution of errors.
      Set the threshold at a chosen PERCENTILE of the normal errors:
      - 99th percentile: flag ~1% of normal transactions (more alerts)
      - 99.9th percentile: flag ~0.1% of normal transactions (fewer alerts)
      → np.percentile(normal_errors, 99.9) gives you this threshold.
    → ALTERNATIVE: use Chebyshev's inequality as a distribution-free bound:
      P(|X - μ| > kσ) ≤ 1/k² for ANY distribution.
      → At k=3: at most 1/9 ≈ 11% of values are flagged. Much weaker than
        the normal distribution's 0.3%, but guaranteed to hold regardless
        of the error distribution's shape.
    → In practice: plot the error distribution, use percentile-based
      thresholds, and tune the percentile based on your false-positive
      tolerance.

PRACTICE:
├── Implement softmax from scratch: 5 lines of numpy
│   → def softmax(z):
│   →     z_stable = z - np.max(z)    # numerical stability (Week 13)
│   →     exp_z = np.exp(z_stable)
│   →     return exp_z / np.sum(exp_z)
│   → Verify: outputs sum to 1, largest input gets largest probability
│
├── Compute reconstruction error by hand:
│   → Input: [1.0, 2.0, 3.0]
│   → Reconstructed: [1.1, 1.8, 3.2]
│   → Error = (1.0-1.1)² + (2.0-1.8)² + (3.0-3.2)² = 0.01 + 0.04 + 0.04 = 0.09
│   → Normal transactions reconstruct with low error; fraud is high.
│
└── PAPER READING EXERCISE (the ultimate test):
    Read the XGBoost paper by Chen & Guestrin (2016), specifically:
    → Section 2.1: Regularized Learning Objective
      - Objective = Σ l(ŷᵢ, yᵢ) + Σ Ω(fₖ)
      - l = loss function (you know this from Week 12)
      - Ω = regularization (you know this from Week 8)
      - fₖ = each tree in the ensemble (you know this from Week 11)
    → Section 2.2: Gradient Tree Boosting
      - Second-order Taylor expansion of the loss
      - Uses gᵢ = ∂l/∂ŷ (first derivative — Week 9-10)
        and hᵢ = ∂²l/∂ŷ² (second derivative — Week 9)
      - Optimal leaf weight: w* = -Σgᵢ / (Σhᵢ + λ)
      - You can now parse this: sum of gradients divided by sum of
        Hessians plus regularization.
    → You won't understand every line. But you should be able to
      follow the STRUCTURE and recognize 80%+ of the notation.
      That's the goal.
```

#### ✅ Week 14 Checkpoint Exercise

```
AUTOENCODER REASONING:

1)  An autoencoder has an encoder with layers [30, 16, 8] and
    decoder with layers [8, 16, 30]. The bottleneck is dimension 8.
    What does the "8" represent?
    Answer: ___

2)  You train this autoencoder on 284,315 normal transactions.
    The reconstruction errors on normal data have:
    mean = 0.12, std = 0.08, median = 0.09,
    99th percentile = 0.35, 99.9th percentile = 0.52

    Why should you NOT just use μ + 3σ = 0.36 as the threshold?
    What threshold would you actually use? Why?

3)  A fraud transaction has reconstruction error 1.45.
    Is it above your chosen threshold from #2? ___
    Why can't the autoencoder reconstruct it well?

4)  Your autoencoder flags 0.5% of transactions as anomalies.
    The actual fraud rate is 0.17%. Is this a problem?
    What metric should you check?

PAPER READING:

5)  From the XGBoost paper, the regularized objective is:
    L(φ) = Σᵢ l(ŷᵢ, yᵢ) + Σₖ Ω(fₖ)
    where Ω(f) = γT + ½λ||w||²

    Translate each symbol:
    l(ŷᵢ, yᵢ) = ___
    Ω(fₖ) = ___
    γ = ___
    T = ___
    λ = ___
    w = ___

6)  The optimal leaf weight is w* = -Σgᵢ / (Σhᵢ + λ).
    Using what you learned in Weeks 9-11, explain in plain English
    what the numerator, denominator, and λ each do.

--- ANSWERS ---

1)  The 8-dimensional bottleneck is a compressed representation of the
    30 original features. Similar to PCA reducing 30 features to 8
    components, but nonlinear. The autoencoder learns which 8-dimensional
    representation best captures the structure of normal transactions.

2)  μ + 3σ = 0.36 assumes the errors are normally distributed. But
    reconstruction errors are bounded below by zero and right-skewed
    (mean 0.12 > median 0.09 confirms the skew). The 3σ rule
    (0.13% of values beyond) doesn't apply to skewed distributions.
    Chebyshev gives a much weaker guarantee: at most 11% beyond 3σ.

    Better: use the 99.9th percentile = 0.52 as the threshold. This
    is distribution-free — it directly says "99.9% of normal
    transactions have error below 0.52." No normality assumption needed.
    Tune the percentile based on your tolerance for false positives.

3)  1.45 >> 0.52 → far above threshold → flagged as anomaly.
    The autoencoder was trained on normal patterns. Fraud transactions
    have different feature relationships that the autoencoder never
    learned to reconstruct. High error = "this doesn't look like
    anything I've seen before."

4)  0.5% flagged but only 0.17% are fraud means many false positives.
    Check PRECISION: of the flagged 0.5%, how many are actually fraud?
    At best, precision = 0.17/0.5 = 34% (if all true fraud is caught).
    This is the precision-recall tradeoff from Week 4.

5)  l(ŷᵢ, yᵢ) = loss function (e.g., cross-entropy for classification)
    Ω(fₖ) = regularization penalty for tree k
    γ = penalty per leaf (controls tree complexity — more leaves = higher penalty)
    T = number of leaves in the tree
    λ = L2 regularization on leaf weights (reg_lambda in XGBoost)
    w = leaf weight vector (the prediction values at each leaf)

6)  Numerator (-Σgᵢ): the sum of negative gradients (pseudo-residuals)
    for all samples in this leaf. Tells you WHICH DIRECTION and HOW
    MUCH to push the prediction.
    Denominator (Σhᵢ + λ): the sum of second derivatives (curvature)
    plus regularization. Tells you HOW CONFIDENT to be in the step.
    High curvature → smaller step (more cautious). Low curvature → bigger
    step. λ adds to the denominator, shrinking the weight toward zero
    (regularization = "be conservative").

PASS CRITERIA: You can explain autoencoder anomaly detection end-to-end
using percentile thresholds (not the 3σ rule), AND read the XGBoost
objective function notation without freezing.
```

---

## 🏁 FINAL GATE — Are You Ready?

```
After Week 14, you should be able to:

[ ] Read Σ, Π, ∂, ∇ notation without hesitation
[ ] Define E[X] and Var(X) and explain why they matter for bias-variance
[ ] Explain Bayes' theorem and the difference between likelihood and posterior
[ ] Manually reproduce a logistic regression prediction from coefficients
[ ] Multiply matrices, compute transposes, explain rank and invertibility
[ ] Explain PCA using eigenvalues/eigenvectors and covariance matrices
[ ] Compute cosine similarity and explain L1 vs L2 sparsity (both arguments)
[ ] Apply the chain rule and compute second derivatives
[ ] Trace through 2D gradient descent and explain convexity
[ ] Diagnose bias vs. variance and prescribe the right fix
[ ] Compute Gini impurity, explain pseudo-residuals, and XGBoost's second-order method
[ ] Compute cross-entropy and focal loss by hand
[ ] Diagnose training problems from loss curve behavior
[ ] Explain autoencoder anomaly detection with percentile-based thresholds
[ ] Read the XGBoost paper's notation and explain the optimal leaf weight formula

If you can check 13/15, you've succeeded.
Greek letters feel like tools, not threats.
```

---

## Quick Reference: Greek Notation Cheat Sheet

```
Symbol   Name          What it means in ML
──────   ─────         ────────────────────
α        alpha         Learning rate / focal loss class weight
β        beta          Momentum coefficient / regression coefficient
γ        gamma         Focal loss modulating exponent / XGBoost leaf penalty
δ        delta         Small change / error term
ε        epsilon       Small constant for numerical stability (e.g., 1e-15)
θ        theta         Model parameters (generic)
λ        lambda        Regularization strength / eigenvalue
μ        mu            Mean / E[X]
σ        sigma         Standard deviation / sqrt(Var(X))
Σ        Sigma (cap)   Summation: add up a series of terms
Π        Pi (cap)      Product: multiply a series of terms
∂        partial       Partial derivative ("with respect to one variable, hold others fixed")
∇        nabla         Gradient vector (collection of partial derivatives)
∈        element of    "belongs to" — x ∈ ℝ means "x is a real number"
||x||    norm          Length/magnitude of vector x (L2 by default)
||x||₁   L1 norm       Sum of absolute values (Manhattan distance)
ℝ        real numbers  The set of all real numbers
ℝⁿ       R-n           n-dimensional real space (n features)
argmin   arg min        "The value of θ that minimizes this expression"
```

---

## Weekly Schedule

```
WEEKDAY (30-45 min):
├── 15-20 min: WATCH one video (3Blue1Brown or StatQuest)
└── 15-25 min: PRACTICE (Khan Academy exercises or notation drill)

WEEKEND (1-2 hours, one session):
├── 30-45 min: ML CONNECTION exercise
│   (reproduce a model's math by hand, connect formula to code)
├── 30-45 min: Khan Academy exercises or review
└── 15 min: Complete the CHECKPOINT EXERCISE for the week.
            Run the Python verification code.
            Write down what clicked and what's still fuzzy.

TOTAL: ~5-7 hours/week
This is sustainable alongside a full-time job.
```

---

## What's Next (After Week 14)

```
If you complete this plan, you have the mathematical foundation to
tackle any of these:

ATTENTION MECHANISMS & TRANSFORMERS:
  → Attention(Q, K, V) = softmax(QKᵀ / √d_k) · V
  → Requires solid matrix multiplication (Week 5), softmax (Week 14),
    transpose (Week 5), and why √d_k is needed (prevents dot products
    from growing with dimension, causing softmax to saturate — ties
    together numerical stability from Week 13 and norms from Week 8).
  → Best learned in a dedicated deep learning course.

VARIATIONAL AUTOENCODERS (VAEs):
  → Build on autoencoders (Week 14) + KL divergence (Week 12)
  → Add a probabilistic twist: the bottleneck is a distribution, not a point

GRAPH NEURAL NETWORKS:
  → Build on linear algebra (adjacency matrices, message passing)
  → Relevant for fraud detection in transaction networks

BAYESIAN DEEP LEARNING:
  → Build on Bayes (Week 2) + neural networks (Week 10)
  → Uncertainty quantification for high-stakes predictions
  → Now you understand why likelihood ≠ posterior, you can properly
    reason about priors, posteriors, and marginal likelihood

REINFORCEMENT LEARNING:
  → Build on optimization (Week 13) + probability (Week 2-3)
  → Different paradigm: learning from rewards, not labels
```