Deep Networks for Dynamic Contracts
I. The Contracting Problem
A principal contracts with an agent in each of infinitely many periods. Productivity z follows a Markov chain on n states with transition matrix P. The agent chooses effort a ∈ [0, 1] in private, and output y ∈ {yL, yH} equals yH with probability π(yH | a) = a. The principal pays consumption c(y) and promises continuation utility w′(y). The agent's flow utility equals u(c) − ψ(a), and both parties discount at β. The value of the principal at the state (w, z) solves
V(w, z) = maxa, c(·), w′(·) Σy π(y | a) [z y − c(y) + β E[V(w′(y), z′) | z]],   (1)
subject to promise keeping and incentive compatibility,
w = −ψ(a) + Σy π(y | a) [u(c(y)) + β w′(y)],   ψ′(a) = Σy πa(y | a) [u(c(y)) + β w′(y)],   (2)
where πa is the derivative of the output probability with respect to effort and w′(y) lies in [wmin, wmax]. Equations (1) and (2) define a functional fixed point for V on the state space [wmin, wmax] × {z1, …, zn}. Value function iteration on a grid of 1,000 promised utilities and n = 15 productivity states takes 11 days.
II. The Method
We represent the value function with a neural network Vθ(w, z) and the policy with a network Pϑ(w, z) that returns effort, consumption, and continuation utilities. Both networks have three hidden layers of 64 units and smooth activation functions. We train the networks on random draws of the state with the loss
L(θ, ϑ) = E[(Vθ(w, z) − (TVθ)(w, z))2] + λ E[rPK2 + rIC2],   (3)
where (TVθ)(w, z) is the right side of (1) evaluated at the policy Pϑ, rPK and rIC are the residuals of the two constraints in (2), and λ is a penalty weight. The algorithm runs in four steps.
Draw a batch of 2,048 states (w, z) uniformly from the state space.
Evaluate the policy network and the value network at the batch, and compute (TVθ) and the two residuals.
Compute the loss (3) and update (θ, ϑ) by stochastic gradient descent with adaptive step sizes.
Repeat for 20,000 iterations, and evaluate the loss on 100,000 fresh draws.
III. Accuracy
TABLE 10—ACCURACY OF THE NEURAL NETWORK SOLUTION
|  | Neural network | Grid iteration |
| --- | --- | --- |
| Mean absolute Bellman residual (share of the mean value) | 0.0004 | 0.0001 |
| Maximum violation of incentive compatibility | 0.0023 | 0.0004 |
| Mean absolute gap to the grid value (percent) | 0.03 | 0 |
| Run time with 15 productivity states | 41 minutes | 11 days |
| Run time with 40 productivity states | 58 minutes | Over 90 days |
Source: Authors' computations on a workstation with one graphics processor. Residuals are evaluated on 100,000 fresh draws of the state.
Table 10 reports the accuracy. The network solution reaches a mean absolute Bellman residual of 0.0004 of the mean value and a mean absolute gap of 0.03 percent to the grid solution. The maximum violation of the incentive constraint equals 0.0023. The run time equals 41 minutes with 15 productivity states and 58 minutes with 40 productivity states, and grid iteration needs 11 days at 15 states.
