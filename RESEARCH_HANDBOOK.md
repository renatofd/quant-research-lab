Crypto Research Lab
Research Handbook
Version 3.0
Status: Beginning of Phase 3
1. Purpose

This project is not a trading strategy.

It is a scientific research framework built on top of Freqtrade.

Its objective is to discover trading systems that are:

statistically robust;
capable of generalization;
resistant to overfitting;
explainable;
reproducible.

The objective is not to maximize Profit Factor on a single backtest.

Every conclusion must be supported by reproducible evidence.

2. Research Philosophy

The project follows a scientific workflow.

Every hypothesis must go through:

Hypothesis

↓

Implementation

↓

Main Research

↓

Robustness

↓

Neighborhood

↓

Walk Forward

↓

Audit

↓

Decision

A hypothesis is only accepted after surviving the complete protocol.

3. Project Evolution
Phase 1 — Infrastructure

Goal:

Build a complete research laboratory.

Implemented:

Experiment Manager
Experiment Database
Backtest Runner
Ranking Engine
Parameter Generator
Strategy Plugin System
Dataset Exporter
Framework Reports

Result:

A modular research infrastructure capable of executing large scientific campaigns.

Phase 2 — Scientific Exploration

Goal:

Discover promising trading architectures.

Several independent research modules were created.

Major topics:

Trend research
Robustness
Neighborhood
Walk Forward
Ablation
Component Variants
Entry Logic
Ensemble
Strategy Synthesizer
Market Eligibility
Trade Pattern Discovery
Domain Decomposition
Signal Opportunity
Filter Information Value

Result:

Most hypotheses were rejected.

This was expected.

The laboratory successfully eliminated large portions of the search space.

4. Scientific Principles

The laboratory values:

Generalization

over

Optimization.

It values:

Consistency

over

Peak Profit Factor.

It values:

Evidence

over

Intuition.

5. Strategies Tested
TrendStrategy

Strengths

Best overall candidate.
Good local robustness.
Stable neighborhood.

Weaknesses

Poor Walk Forward.
Severe temporal overfitting.

Status

Research continues.

PullbackStrategy

Results consistently inferior.

Status

Discarded.

MeanReversionStrategy

Created to test an entirely different market hypothesis.

Results

isolated high PF values
zero robust regions
failed Walk Forward

Status

Discarded.

N-of-M Trend Confirmation

Automatically synthesized.

Strengths

better distribution
fewer empty folds

Weaknesses

PF OOS still below one
Survival still poor

Status

Interesting but insufficient.

Ensemble

Tested:

Majority Voting
Weighted Voting
Confidence Voting
Dynamic Expert
Bandit
Regime Expert
Pair Expert

No architecture consistently beat individual strategies.

Status

Discarded.

6. Main Discoveries
Walk Forward

Biggest scientific filter.

Excellent in-sample performance frequently collapsed OOS.

Conclusion

Optimization ≠ Generalization.

Neighborhood

Many experiments were not isolated peaks.

However:

Neighborhood stability does not imply Walk Forward stability.

Robustness

Several experiments had excellent PF.

Very few produced true robust regions.

ATR

ATR became the most important component discovered.

Evidence:

highest Information Gain

highest protection against losses

highest elimination of winners

Interpretation

ATR is extremely informative.

Removing ATR is not supported.

Current hypothesis:

ATR should become adaptive.

Volume

Repeatedly appears as:

high cost

limited demonstrated benefit

Candidate for controlled relaxation.

Breakout

Similar behavior.

Strong candidate for controlled relaxation.

Market Eligibility

Research included:

weekdays
hours
sessions
trading pairs

Findings:

Tuesday

Friday

NY session

performed better in-sample.

No filter generalized sufficiently.

Nothing promoted to production.

Domain Decomposition

Strong evidence suggests:

One universal strategy is probably inadequate.

Two natural pair clusters emerged.

Some assets deserve dedicated research.

Single Asset Research

AVAX

Rejected.

LTC

Most promising asset found.

Reasons

many PF>1 neighbors

high local robustness

However

no robust formal region

no convincing Walk Forward

still under investigation

Signal Opportunity

One of the most important discoveries.

The problem is not:

lack of opportunities.

The problem is:

too many hard filters.

Filter Information Value

Most important conclusion.

ATR

very informative

Volume

likely too restrictive

Breakout

likely too restrictive

No evidence supports removing filters.

Only controlled experimentation.

7. Research Mistakes

Several lessons were learned.

Never trust:

high PF with few trades

Never promote:

local optimum

Never assume:

Neighborhood implies robustness

Never assume:

Robustness implies generalization

Never optimize:

without Walk Forward

8. Current Scientific Consensus

Current evidence suggests:

Trend following still contains the strongest hypothesis.

The problem is not the indicators.

The problem is likely:

decision architecture

plus

filter rigidity.

9. Current Bottleneck

Observational research has reached its limit.

The laboratory cannot answer questions like:

"What would have happened if ATR had not blocked this trade?"

Those trades never happened.

Therefore:

counterfactuals are unavailable.

This means:

Correlation has reached its limit.

The next phase requires intervention.

10. Phase 3

Phase 3 changes the nature of the laboratory.

From:

Observational Science

To:

Experimental Science

11. Phase 3 Goal

Discover

which components actually create alpha.

Not

which parameter gives the highest PF.

12. Experimental Philosophy

Every experiment changes exactly one variable.

Example

Trend

↓

Trend without Volume

Everything else remains identical.

Another example

Trend

↓

Trend with adaptive ATR

Nothing else changes.

13. Current Priority List

Highest priority

Adaptive ATR

Second

Volume relaxation

Third

Breakout relaxation

Fourth

Adaptive Threshold

Fifth

Regime-dependent filters

14. What Should NOT Be Done

Do not create random strategies.

Do not create more ensembles.

Do not enlarge Hyperopt space.

Do not optimize dozens of parameters simultaneously.

Do not trust isolated PF.

Do not trust few-trade experiments.

15. Acceptance Criteria

A hypothesis must improve simultaneously:

Profit Factor

Walk Forward

Robustness

Survival

Stability

Trade count

Generalization

Otherwise

it is rejected.

16. Long-Term Vision

The laboratory should eventually become capable of answering questions such as:

"Does ATR actually improve trading?"

"Does volume really matter?"

"Should breakout be adaptive?"

"Which filters contribute independent information?"

Instead of merely answering:

"What is the best parameter?"

17. Current Project Status

Infrastructure

Complete.

Scientific framework

Complete.

Research framework

Complete.

Data collection

Complete.

Observational science

Largely complete.

Experimental science

Starting now.

18. Development Rules

Every new module must answer one explicit scientific hypothesis.

No module may be created simply because it seems interesting.

Every module must have:

a clear hypothesis;
measurable success criteria;
reproducible outputs;
no changes to operational strategies unless explicitly authorized.
19. Immediate Next Objective

The next milestone is not another strategy.

It is the first causal intervention campaign.

Example hypotheses:

Does relaxing the Volume filter increase trade count without harming generalization?
Does an adaptive ATR outperform the current fixed ATR?
Does a softer Breakout filter improve Walk Forward results?
Does a regime-aware threshold outperform a static threshold?

These experiments should modify one component at a time, then run the full scientific protocol (main research, robustness, neighborhood, walk-forward and audit) before accepting or rejecting the hypothesis.