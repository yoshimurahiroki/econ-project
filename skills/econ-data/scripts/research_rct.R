# Official assignment, estimation and design diagnosis for research_causal.py.
# This file owns the RCT calculation; Python owns the public entry and persistence.
suppressPackageStartupMessages(library(jsonlite))
args <- commandArgs(trailingOnly = TRUE)
s <- fromJSON(args[1], simplifyVector = FALSE)
o <- s$options
fail <- function(message) stop(message, call. = FALSE)
check_fields <- function(x, required, optional, name) {
  if (!is.list(x) || !all(required %in% names(x)) ||
      length(setdiff(names(x), c(required, optional))))
    fail(paste(name, "requires", paste(required, collapse = ", "),
               "and accepts", paste(optional, collapse = ", ")))
}
number <- function(x, name, lower = -Inf, upper = Inf, integer = FALSE) {
  if (!is.numeric(x) || length(x) != 1L || !is.finite(x) ||
      x < lower || x > upper || (integer && x != floor(x)))
    fail(paste(name, "has an invalid numeric value"))
  x
}
check_fields(o, c("operation", "treatment", "seed", "experimental_design"),
  c("estimator", "contrasts", "ri", "simulation", "assignment_result", "weights",
    "receipt", "confidence_level", "definitions"), "RCT options")
if (!o$operation %in% c("assign", "analyze", "diagnose"))
  fail("RCT operation must be assign, analyze or diagnose")
if (!identical(s$inference, list(type = "official")))
  fail('RCT design requires inference={"type":"official"}')
ed <- o$experimental_design
check_fields(ed, "interference", c("conditions", "blocks", "clusters", "prob_each",
  "m_each", "block_prob_each", "block_m_each", "factorial", "ra_type", "formula",
  "prob", "prob_unit", "prob_unit_each"), "experimental_design")
if (!is.null(ed$ra_type) && !identical(ed$ra_type, "balanced"))
  fail('experimental_design.ra_type selects the native "balanced" design')
balanced <- identical(ed$ra_type, "balanced") || !is.null(ed$formula) || !is.null(ed[["prob_unit_each"]])
if (!is.null(ed[["prob_unit"]]) && !balanced)
  fail('Unit-specific probabilities require ra_type="balanced"')
if (!ed$interference %in% c("none", "within_cluster") ||
    (ed$interference == "within_cluster" && is.null(ed$clusters)))
  fail("Declare no interference, or within_cluster interference with a cluster column")
if (length(s$endogenous) || length(s$instruments))
  fail("RCT design estimates assignment effects; receipt LATE uses the existing IV owner")
seed <- number(o$seed, "seed", 0, .Machine$integer.max, TRUE)
level <- if (is.null(o$confidence_level)) .95 else number(o$confidence_level, "confidence_level", 0, 1)
if (level %in% c(0, 1)) fail("confidence_level must be strictly between zero and one")
alpha <- 1 - level
for (p in c("randomizr", "estimatr"))
  if (!requireNamespace(p, quietly = TRUE)) fail(paste("Install the declared R dependency", p))
if (packageVersion("estimatr") < "2.0.1")
  fail("RCT design requires estimatr >= 2.0.1 for declaration-based multi-arm HT variance")

factor_cells <- NULL
if (!is.null(ed$factorial)) {
  factors <- lapply(ed$factorial, unlist)
  if (!length(factors) || is.null(names(factors)) || any(!nzchar(names(factors))) ||
      any(vapply(factors, function(x) length(x) != 2L || anyDuplicated(x) || any(!nzchar(x)), logical(1))))
    fail("factorial maps each factor name to two distinct level labels")
  if (!is.null(ed$conditions)) fail("factorial generates its cell conditions from factor levels")
  factor_cells <- expand.grid(factors, KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
  conditions <- apply(factor_cells, 1, function(x) paste(paste(names(factors), x, sep = "="), collapse = "|"))
  factor_cells$condition <- conditions
} else {
  conditions <- unlist(ed$conditions, use.names = FALSE)
  if (!is.character(conditions) || length(conditions) < 2L || anyDuplicated(conditions) || any(!nzchar(conditions)))
    fail("conditions must contain at least two distinct string labels in their adopted order")
}
d <- if (exists("ers_read_table", mode = "function")) ers_read_table(args[2], text_columns = TRUE) else
  read.csv(args[2], check.names = FALSE, stringsAsFactors = FALSE, colClasses = "character")
if (any(startsWith(names(d), ".ers_"))) fail("Input columns must not use the reserved .ers_ prefix")
N <- nrow(d)
if (N < 2L || !s$id %in% names(d) || anyNA(d[[s$id]]) || any(!nzchar(trimws(d[[s$id]]))) || anyDuplicated(d[[s$id]]))
  fail("RCT requires at least two unique nonempty observation IDs")
ids <- d[[s$id]]
read_column <- function(name, numeric = FALSE) {
  if (is.null(name)) return(NULL)
  if (!is.character(name) || length(name) != 1L || !name %in% names(d))
    fail(paste("Missing RCT column", name))
  x <- d[[name]]
  if (numeric) {
    x <- suppressWarnings(as.numeric(x))
    if (any(!is.finite(x))) fail(paste(name, "must be finite numeric data"))
  } else if (anyNA(x) || any(!nzchar(trimws(x)))) fail(paste(name, "must contain nonempty labels"))
  x
}
blocks <- read_column(ed$blocks)
clusters <- read_column(ed$clusters)
block_labels <- if (is.null(blocks)) "all" else sort(unique(blocks))
block_id <- if (is.null(blocks)) rep("all", N) else blocks
assignment_id <- if (is.null(clusters)) ids else clusters
if (!is.null(clusters) && any(vapply(split(block_id, clusters), function(x) length(unique(x)) != 1L, logical(1))))
  fail("Every assignment cluster must belong to one block")
weights <- if (is.null(o$weights)) rep(1, N) else read_column(o$weights, TRUE)
if (any(weights <= 0)) fail("Population weights must be strictly positive")
covariates <- unlist(s$regressors, use.names = FALSE)
if (o$treatment %in% covariates || s$outcome %in% covariates)
  fail("RCT regressors contain only prespecified pretreatment covariates")
X <- if (length(covariates)) as.matrix(as.data.frame(setNames(lapply(covariates, read_column, numeric = TRUE), covariates))) else NULL

ra_args <- list(N = N, conditions = conditions)
if (!is.null(blocks)) ra_args$blocks <- blocks
if (!is.null(clusters)) ra_args$clusters <- clusters
allocation_fields <- intersect(names(ed), c("prob_each", "m_each", "block_prob_each", "block_m_each"))
if (length(allocation_fields) > 1L) fail("Choose one allocation probability or count specification")
for (nm in allocation_fields) {
  v <- ed[[nm]]
  if (startsWith(nm, "block_")) {
    if (is.null(blocks) || is.null(names(v)) || !setequal(names(v), block_labels))
      fail(paste(nm, "must name every block label exactly once"))
    v <- do.call(rbind, lapply(v[block_labels], unlist, use.names = FALSE))
    if (ncol(v) != length(conditions)) fail(paste(nm, "must have one entry per condition"))
  } else v <- unlist(v, use.names = FALSE)
  ra_args[[nm]] <- v
}
if (balanced) {
  if (!all(c("ra_type", "formula", "prob_unit", "prob_unit_each") %in% names(formals(randomizr::declare_ra))) ||
      !"balanced_ra" %in% getNamespaceExports("randomizr"))
    fail("Balanced allocation requires the pinned randomizr balanced_ra/declaration interface")
  if (length(intersect(allocation_fields, c("m_each", "block_m_each", "block_prob_each"))))
    fail("Balanced assignment uses native probabilities; fixed counts remain in the complete-design contract")
  probability_fields <- intersect(names(ed), c("prob", "prob_each", "prob_unit", "prob_unit_each"))
  if (length(probability_fields) > 1L) fail("Choose one balanced assignment probability specification")
  ra_args$ra_type <- "balanced"
  if (!is.null(ed[["prob"]])) ra_args$prob <- number(ed[["prob"]], "balanced prob", 0, 1)
  if (!is.null(ed[["prob_unit"]])) ra_args$prob_unit <- read_column(ed[["prob_unit"]], TRUE)
  if (!is.null(ed[["prob_unit_each"]])) {
    probability_columns <- unlist(ed[["prob_unit_each"]], use.names = FALSE)
    if (!is.character(probability_columns) || length(probability_columns) != length(conditions) || anyDuplicated(probability_columns))
      fail("prob_unit_each names one distinct probability column per condition in the adopted order")
    ra_args$prob_unit_each <- do.call(cbind, lapply(probability_columns, read_column, numeric = TRUE))
  }
  if (!is.null(ed$formula)) {
    if (!is.character(ed$formula) || length(ed$formula) != 1L ||
        length(conditions) != 2L || !is.null(blocks) || !is.null(ed[["prob_unit_each"]]))
      fail("Native cube-on-X uses one two-arm formula, with optional clusters and without blocks or prob_unit_each")
    for (column in covariates) d[[column]] <- read_column(column, TRUE)
    balance_formula <- as.formula(ed$formula, env = list2env(as.list(d), parent = environment()))
    if (length(balance_formula) != 2L || !all(all.vars(balance_formula) %in% covariates))
      fail("The balancing formula must be one-sided and use only the declared pretreatment regressors")
    ra_args$formula <- balance_formula
    # declare_ra expands prob_each into a matrix, which its formula path excludes.
    if (!is.null(ra_args$prob_each)) {
      pe <- ra_args$prob_each
      if (!is.numeric(pe) || length(pe) != 2L || any(!is.finite(pe)) ||
          any(pe < 0 | pe > 1) || abs(sum(pe) - 1) > 1e-8)
        fail("Two-arm prob_each must contain two probabilities summing to one")
      ra_args$prob <- pe[2L]
      ra_args$prob_each <- NULL
    }
  }
} else if (!is.null(ed[["prob"]])) {
  fail('The scalar prob option belongs to ra_type="balanced"; complete designs retain prob_each')
}
declaration <- do.call(randomizr::declare_ra, ra_args)
balancing_matrix <- if (balanced) declaration$.X else NULL
probabilities <- declaration$probabilities_matrix
if (any(!is.finite(probabilities)) || any(probabilities <= 0 | probabilities >= 1))
  fail("Every unit must have positive assignment probability in every declared condition")
colnames(probabilities) <- conditions
design_name <- sub("^ra_", "", class(declaration)[2])
if (!balanced && length(conditions) > 2L) for (b in block_labels) {
  ix <- which(block_id == b & !duplicated(assignment_id))
  counts <- length(ix) * probabilities[ix[1], ]
  if (any(abs(counts - round(counts)) > 1e-10))
    fail(paste("Multi-arm inference requires fixed integer arm counts in each block; supply m_each/block_m_each or matching probabilities for block", b))
}

if (is.null(o$contrasts)) {
  if (is.null(factor_cells)) {
    contrasts <- lapply(seq.int(2L, length(conditions)), function(j) {
      v <- numeric(length(conditions)); v[c(1L, j)] <- c(-1, 1)
      list(name = paste0(conditions[j], " - ", conditions[1]), weights = setNames(as.list(v), conditions))
    })
  } else {
    contrasts <- list()
    for (k in seq_along(factors)) for (subset in combn(names(factors), k, simplify = FALSE)) {
      sign <- Reduce(`*`, lapply(subset, function(nm) ifelse(factor_cells[[nm]] == factors[[nm]][2], 1, -1)))
      contrasts[[length(contrasts) + 1L]] <- list(name = paste(subset, collapse = ":"),
        weights = setNames(as.list(sign / 2^(length(factors) - 1L)), conditions))
    }
  }
} else contrasts <- o$contrasts
if (!is.list(contrasts) || !length(contrasts)) fail("contrasts must be a nonempty list")
C <- do.call(rbind, lapply(contrasts, function(x) {
  check_fields(x, c("name", "weights"), character(), "contrast")
  v <- unlist(x$weights)
  if (!is.character(x$name) || length(x$name) != 1L || !nzchar(x$name) ||
      !is.numeric(v) || !setequal(names(v), conditions) || any(!is.finite(v)) ||
      abs(sum(v)) > 1e-12 || !any(v != 0)) fail("Each contrast names finite zero-sum weights for all conditions")
  v[conditions]
}))
rownames(C) <- vapply(contrasts, `[[`, character(1), "name")
colnames(C) <- conditions
if (anyDuplicated(rownames(C))) fail("Contrast names must be unique")
pairs <- apply(C, 1, function(v) sum(v == -1) == 1L && sum(v == 1) == 1L && sum(v != 0) == 2L)
estimator <- if (!is.null(o$estimator)) o$estimator else if (balanced || (all(pairs) && !length(covariates))) "horvitz_thompson" else "lm_robust"
if (!estimator %in% c("horvitz_thompson", "lm_robust", "difference_in_means"))
  fail("estimator must be horvitz_thompson, lm_robust or difference_in_means")
if (balanced && estimator != "horvitz_thompson")
  fail("Balanced designs use native probability-weighted HT contrasts with design-matched Monte Carlo randomization inference")
if (!balanced && estimator != "lm_robust" && (!all(pairs) || length(covariates)))
  fail("General cell contrasts and covariate adjustment require lm_robust")
if (estimator == "difference_in_means" && (length(conditions) != 2L || !is.null(clusters) || !is.null(o$weights)))
  fail("difference_in_means uses the unweighted two-arm individual/block complete design; choose HT or lm_robust for this design")
se_type <- if (balanced) "none" else if (estimator == "horvitz_thompson") "youngs" else if (estimator == "difference_in_means") "default" else if (is.null(clusters)) "HC2" else "CR2"

RNGkind("L'Ecuyer-CMRG")
set.seed(seed)
rng_before <- .Random.seed
if (o$operation == "assign") {
  if (o$treatment %in% names(d)) fail("Assignment creation requires a roster without an existing treatment column")
  z <- as.character(randomizr::conduct_ra(declaration))
} else if (o$operation == "analyze") z <- read_column(o$treatment) else z <- NULL
rng_after <- .Random.seed
if (!is.null(z)) {
  if (!all(z %in% conditions)) fail("Observed assignments must use the declared condition labels")
  if (any(vapply(split(z, assignment_id), function(x) length(unique(x)) != 1L, logical(1))))
    fail("Treatment assignments must be constant within assignment units")
  if (!balanced) for (b in block_labels) {
    ix <- which(block_id == b & !duplicated(assignment_id))
    counts <- tabulate(match(z[ix], conditions), nbins = length(conditions))
    expected <- length(ix) * probabilities[ix[1], ]
    floor_counts <- floor(expected + 1e-10)
    if (any(counts < floor_counts | counts > ceiling(expected - 1e-10)))
      fail(paste("Observed arm counts contradict the declared randomization in block", b))
  }
}
if (nzchar(args[4])) {
  saved <- fromJSON(args[4], simplifyVector = FALSE)
  a <- saved$diagnostics$assignment
  if (o$operation != "analyze" || !identical(unlist(a$ids), ids) ||
      !identical(unlist(a$condition), z) || !identical(unlist(a$assignment_ids), assignment_id) ||
      !identical(unlist(a$blocks), blocks) ||
      !isTRUE(all.equal(do.call(rbind, lapply(a$probabilities, unlist)), unname(probabilities), check.attributes = FALSE)))
    fail("Analysis must match the saved assignment's design, seed, IDs, units, probabilities and labels")
  if (!is.null(balancing_matrix) &&
      (!identical(unlist(a$balancing_columns, use.names = FALSE), colnames(balancing_matrix)) ||
       !isTRUE(all.equal(do.call(rbind, lapply(a$balancing_matrix, unlist)),
                         unname(balancing_matrix), check.attributes = FALSE))))
    fail("Analysis must retain the balancing matrix from the saved assignment")
}

estimate_outcome <- function(y, assignment, ci = TRUE, retain = FALSE) {
  ci <- ci && !balanced
  observed <- is.finite(y)
  if (sum(observed) < 2L) fail("Estimation needs at least two observed outcomes")
  dat <- data.frame(.ers_y = y, .ers_z = factor(assignment, levels = conditions),
    .ers_w = weights, .ers_block = factor(block_id, levels = block_labels))
  if (!is.null(clusters)) dat$.ers_cluster <- factor(clusters)
  rows <- vector("list", nrow(C)); fits <- vector("list", nrow(C)); covariance <- NULL
  if (estimator == "lm_robust") {
    cells <- expand.grid(condition = conditions, block = block_labels, stringsAsFactors = FALSE)
    design_matrix <- vapply(seq_len(nrow(cells)), function(j)
      as.numeric(block_id == cells$block[j] & assignment == cells$condition[j]), numeric(N))
    block_mass <- tapply(weights[observed], factor(block_id[observed], levels = block_labels), sum)
    if (anyNA(block_mass)) fail("Each block must retain observed outcomes")
    block_mass <- block_mass / sum(block_mass)
    L <- C[, match(cells$condition, conditions), drop = FALSE] *
      rep(block_mass[match(cells$block, block_labels)], each = nrow(C))
    if (!is.null(X)) for (j in seq_len(ncol(X))) {
      centers <- tapply(seq_len(N), block_id, function(i) weighted.mean(X[i[observed[i]], j], weights[i[observed[i]]]))
      centered <- X[, j] - as.numeric(centers[block_id])
      design_matrix <- cbind(design_matrix, design_matrix[, seq_len(nrow(cells)), drop = FALSE] * centered)
      L <- cbind(L, matrix(0, nrow(C), nrow(cells)))
    }
    if (qr(design_matrix[observed, , drop = FALSE])$rank != ncol(design_matrix))
      fail("The adopted block-cell/covariate regression must have full rank in the observed sample")
  }
  for (j in seq_len(nrow(C))) {
    if (balanced) {
      # Native HT pair estimates share one population denominator. A zero-sum
      # contrast is their declared linear combination against the reference arm.
      reference <- which(C[j, ] != 0)[1L]
      active <- which(C[j, ] != 0 & seq_along(conditions) != reference)
      arm_fits <- lapply(active, function(k) {
        selected <- observed & assignment %in% conditions[c(reference, k)]
        probability_pair <- probabilities[selected, c(reference, k), drop = FALSE]
        adjusted <- dat
        adjusted$.ers_y <- y * weights * sum(observed) / sum(weights[observed])
        estimatr::horvitz_thompson(.ers_y ~ .ers_z, data = adjusted,
          condition_prs = probability_pair, condition1 = conditions[reference], condition2 = conditions[k],
          se_type = "none", ci = FALSE, alpha = alpha)
      })
      estimate <- sum(C[j, active] * vapply(arm_fits, function(fit) unname(fit$coefficients[1]), numeric(1)))
      if (!is.finite(estimate)) fail("Native HT returned a nonfinite balanced-design contrast")
      rows[[j]] <- data.frame(term = rownames(C)[j], estimate = estimate, se = NA_real_,
        p_value = NA_real_, ci_low = NA_real_, ci_high = NA_real_, df = NA_real_, n = sum(observed))
      if (retain) fits[[j]] <- arm_fits
      next
    }
    if (estimator == "lm_robust") {
      # A reversible basis change makes the requested population contrast an
      # actual coefficient. estimatr then returns its own HC2/CR2 df and CI.
      pivot <- which(L[j, ] != 0)[1]
      transform <- diag(ncol(design_matrix)); transform[pivot, ] <- L[j, ]
      inverse <- solve(transform)
      transformed <- design_matrix %*% inverse
      colnames(transformed) <- paste0(".ers_x", seq_len(ncol(transformed)))
      fitted_data <- cbind(dat, transformed)
      call <- list(formula = reformulate(colnames(transformed), response = ".ers_y", intercept = FALSE),
        data = fitted_data, weights = fitted_data$.ers_w, se_type = if (ci) se_type else "none", ci = ci, alpha = alpha)
      if (!is.null(clusters)) call$clusters <- fitted_data$.ers_cluster
      fit <- do.call(estimatr::lm_robust, call)
      index <- pivot
      if (ci && j == 1L) {
        linear <- L %*% inverse
        covariance <- linear %*% fit$vcov %*% t(linear)
      }
    } else {
      c1 <- conditions[C[j, ] == -1]; c2 <- conditions[C[j, ] == 1]
      call <- list(formula = .ers_y ~ .ers_z, data = dat,
        condition1 = c1, condition2 = c2, se_type = if (ci) se_type else "none", ci = ci, alpha = alpha)
      if (estimator == "horvitz_thompson") {
        call$data$.ers_y <- y * weights * sum(observed) / sum(weights[observed])
        call$condition_prs <- declaration
        fit <- do.call(estimatr::horvitz_thompson, call)
      } else {
        if (!is.null(blocks)) call$blocks <- dat$.ers_block
        fit <- do.call(estimatr::difference_in_means, call)
      }
      index <- 1L
    }
    row <- data.frame(term = rownames(C)[j], estimate = unname(fit$coefficients[index]),
      se = if (ci) unname(fit$std.error[index]) else NA_real_,
      p_value = if (ci) unname(fit$p.value[index]) else NA_real_,
      ci_low = if (ci) unname(fit$conf.low[index]) else NA_real_,
      ci_high = if (ci) unname(fit$conf.high[index]) else NA_real_,
      df = if (ci) unname(fit$df[index]) else NA_real_, n = sum(observed), stringsAsFactors = FALSE)
    needed <- if (ci) c("estimate", "se", "p_value", "ci_low", "ci_high") else "estimate"
    if (any(!is.finite(unlist(row[needed])))) fail(paste("Official estimator returned nonfinite inference for", row$term))
    rows[[j]] <- row
    if (retain) fits[[j]] <- fit
  }
  if (is.null(covariance) && nrow(C) == 1L && ci) covariance <- matrix(rows[[1]]$se^2, 1, 1)
  list(rows = do.call(rbind, rows), fits = if (retain) fits else NULL, covariance = covariance)
}

ri <- o$ri
if (balanced && o$operation != "assign" && (is.null(ri) || !identical(ri$method, "monte_carlo")))
  fail("Balanced analysis and diagnosis require Monte Carlo randomization inference from the actual declaration")
if (balanced && !is.null(ri) && identical(ri$method, "exact"))
  fail("randomizr does not enumerate balanced-design assignment probabilities; select monte_carlo")
if (!is.null(ri)) {
  check_fields(ri, c("method", "seed"), c("draws", "maximum_permutations", "null_effects"), "randomization inference")
  if (!ri$method %in% c("exact", "monte_carlo")) fail("RI method must be exact or monte_carlo")
  number(ri$seed, "RI seed", 0, .Machine$integer.max, TRUE)
  null_effects <- if (is.null(ri$null_effects)) setNames(rep(0, length(conditions)), conditions) else unlist(ri$null_effects)
  if (!is.numeric(null_effects) || !setequal(names(null_effects), conditions) || any(!is.finite(null_effects)) || null_effects[conditions[1]] != 0)
    fail("RI null_effects must name every condition, with zero for the reference condition")
  null_effects <- null_effects[conditions]
  if (ri$method == "exact") {
    limit <- if (is.null(ri$maximum_permutations)) 10000L else number(ri$maximum_permutations, "maximum_permutations", 1, Inf, TRUE)
    support_size <- randomizr::obtain_num_permutations(declaration)
    if (!is.finite(support_size) || support_size > limit) fail("Exact RI exceeds maximum_permutations; adopt monte_carlo with its draw count")
    permutations <- randomizr::obtain_permutation_matrix(declaration, maximum_permutations = limit)
    permutation_probabilities <- randomizr::obtain_permutation_probabilities(declaration)
    if (ncol(permutations) != length(permutation_probabilities) || abs(sum(permutation_probabilities) - 1) > 1e-10)
      fail("Official permutation columns and probabilities do not agree")
    for (j in seq_along(conditions)) if (max(abs((permutations == conditions[j]) %*% permutation_probabilities - probabilities[, j])) > 1e-10)
      fail("Official permutation probabilities do not recover declared marginal assignment probabilities")
  } else number(ri$draws, "RI draws", 1, Inf, TRUE)
}
randomization_test <- function(y, assignment, draw_seed = ri$seed) {
  rng <- .Random.seed
  on.exit(base::assign(".Random.seed", rng, envir = .GlobalEnv))
  set.seed(draw_seed)
  base <- y - null_effects[match(assignment, conditions)]
  null_contrasts <- drop(C %*% null_effects)
  observed <- abs(estimate_outcome(y, assignment, FALSE)$rows$estimate - null_contrasts)
  if (ri$method == "exact") {
    draws <- permutations; pr <- permutation_probabilities
  } else {
    draws <- replicate(ri$draws, as.character(randomizr::conduct_ra(declaration)))
    pr <- rep(1 / ri$draws, ri$draws)
  }
  statistics <- vapply(seq_len(ncol(draws)), function(k) {
    zz <- as.character(draws[, k])
    yy <- base + null_effects[match(zz, conditions)]
    abs(estimate_outcome(yy, zz, FALSE)$rows$estimate - null_contrasts)
  }, numeric(nrow(C)))
  statistics <- matrix(statistics, nrow = nrow(C))
  exceed <- statistics >= observed - 1e-12 * pmax(1, observed)
  p <- if (ri$method == "exact") drop(exceed %*% pr) else (rowSums(exceed) + 1) / (ncol(draws) + 1)
  list(method = ri$method, seed = draw_seed, statistic = "absolute centered assignment-effect estimate",
    sharp_null = "Y_i(a) = Y_i(reference) + null_effects[a] for every unit and every condition; observation status is fixed across assignments",
    null_effects = as.list(null_effects), draws = ncol(draws),
    sampling = if (ri$method == "exact") "complete enumeration weighted by obtain_permutation_probabilities" else "independent conduct_ra draws from the declared design; (1+exceedances)/(1+draws)",
    p_values = setNames(as.list(p), rownames(C)),
    observed_statistics = setNames(as.list(observed), rownames(C)),
    statistics = unname(statistics),
    permutation_probabilities = if (ri$method == "exact") I(pr) else NULL)
}

adopted_design <- modifyList(ed, list(design = design_name, conditions = I(conditions),
  assignment_unit = if (is.null(clusters)) s$id else ed$clusters,
  assignment_units = length(unique(assignment_id)), observations = N,
  block_order = I(block_labels), factorial_cells = factor_cells,
  estimator = paste0("estimatr::", estimator), se_type = se_type,
  reference_distribution = if (balanced) "declared assignment distribution under the sharp null" else if (estimator == "horvitz_thompson") "normal" else "official contrast-specific t",
  probability_function = if (balanced) "randomizr::balanced_ra_probabilities" else "randomizr declaration probabilities",
  assignment_function = if (balanced) "randomizr::balanced_ra via conduct_ra" else "randomizr::conduct_ra",
  independent_draw_unit = if (balanced) "complete declared assignment vector" else NULL,
  allocation_dependence = if (balanced) "joint cube allocation across assignment units" else NULL,
  average_effect_covariance_available = if (balanced) FALSE else NULL,
  balance = if (is.null(balancing_matrix)) NULL else list(formula = ed$formula,
    columns = I(colnames(balancing_matrix)),
    assignment_scale = if (is.null(clusters)) "observation covariates" else "unweighted cluster means of observation covariates",
    target = "X'Z near X'pi; native cube landing determines attained balance",
    matrix_ref = "diagnostics.assignment.balancing_matrix"),
  contrasts = contrasts,
  seed = seed, rng_kind = I(RNGkind()), effect_target = "population-weighted assignment ITT",
  weights = list(column = o$weights, normalization = "fixed population weights normalized over observed outcome units"),
  outcome_observation = "complete outcomes for analysis; diagnosis uses assignment-independent MCAR retention",
  measurement_period = s$period))
if (!is.null(ri)) adopted_design$randomization_inference <- list(specification = ri,
  sharp_null = "Y_i(a) = Y_i(reference) + null_effects[a] for every unit and every condition; observation status is fixed across assignments",
  null_effects = as.list(null_effects),
  sampling = if (ri$method == "exact") "complete enumeration with official assignment probabilities" else "independent conduct_ra draws with the plus-one Monte Carlo p value")
versions <- lapply(c("randomizr", "estimatr", "jsonlite"), function(p) as.character(packageVersion(p)))
names(versions) <- c("randomizr", "estimatr", "jsonlite")
result <- list(result_format_version = 1, method = "rct_design", engine = paste0("randomizr + estimatr::", estimator),
  versions = c(versions, list(R = as.character(getRversion()))), options = o,
  adopted = c(s[c("population", "period", "unit", "estimand", "identification", "assignment", "inference")],
    list(experimental_design = adopted_design, assignment_unit = adopted_design$assignment_unit, weights = adopted_design$weights)),
  sample = list(id_column = s$id, input_rows = N, observations = N, included_ids = I(ids), included_ids_available = TRUE),
  diagnostics = list(assignment = list(ids = I(ids), assignment_ids = I(assignment_id),
    condition = if (is.null(z)) NULL else I(z), blocks = if (is.null(blocks)) NULL else I(blocks),
    clusters = if (is.null(clusters)) NULL else I(clusters), conditions = I(conditions),
    probabilities = unname(probabilities), realized_probability = if (is.null(z)) NULL else I(probabilities[cbind(seq_len(N), match(z, conditions))]),
    population_weights = I(weights), rng_before = I(rng_before), rng_after = I(rng_after),
    balancing_matrix = if (is.null(balancing_matrix)) NULL else unname(balancing_matrix),
    balancing_columns = if (is.null(balancing_matrix)) NULL else I(colnames(balancing_matrix))),
    n_clusters = if (is.null(clusters)) NULL else length(unique(clusters))),
  runtime = list(library_paths = I(.libPaths()), working_directory = getwd(),
    profile_user = Sys.getenv("R_PROFILE_USER", unset = NA_character_)),
  signature = list(declare_ra = names(formals(randomizr::declare_ra)), conduct_ra = names(formals(randomizr::conduct_ra)),
    estimator = names(formals(getExportedValue("estimatr", estimator)))))
metadata <- modifyList(if (is.null(o$definitions)) list() else o$definitions, list(experimental_design = adopted_design, unit = s$unit, population = s$population,
  period = s$period, estimand = s$estimand, assignment_unit = adopted_design$assignment_unit,
  observation_unit = s$id, inference_unit = adopted_design$assignment_unit, weights = adopted_design$weights,
  estimator = paste0("estimatr::", estimator), inference = list(type = "official", se_type = se_type),
  n = N, n_clusters = result$diagnostics$n_clusters,
  interval_type = if (balanced) "none; Monte Carlo sharp-null p values" else "pointwise", confidence_level = level))
if (balanced) {
  result$signature$balanced_ra <- names(formals(randomizr::balanced_ra))
  result$signature$balanced_ra_probabilities <- names(formals(randomizr::balanced_ra_probabilities))
  metadata$inference_unit <- "complete declared assignment vector"
}
native <- list(declaration = declaration, ids = ids, assignment = z, data = d)
if (o$operation == "assign") {
  rows <- data.frame(condition = conditions,
    observations = as.integer(table(factor(z, levels = conditions))),
    assignment_units = as.integer(table(factor(z[!duplicated(assignment_id)], levels = conditions))), stringsAsFactors = FALSE)
  result$display <- list(kind = "table", rows = rows, metadata = metadata)
} else if (o$operation == "analyze") {
  y <- read_column(s$outcome, TRUE)
  fitted <- estimate_outcome(y, z, retain = TRUE)
  result$estimates <- fitted$rows
  result$covariance <- fitted$covariance
  result$covariance_terms <- I(rownames(C))
  result$display <- list(kind = "coefficient", rows = fitted$rows, metadata = metadata)
  native$fit <- fitted$fits
  if (!is.null(o$receipt)) {
    receipt <- read_column(o$receipt)
    result$diagnostics$receipt <- list(column = o$receipt, observed = I(receipt),
      assignment_by_receipt = as.data.frame(table(assignment = z, receipt = receipt)))
  }
  if (!is.null(ri)) {
    result$diagnostics$randomization_inference <- randomization_test(y, z)
    if (balanced) {
      result$estimates$p_value <- unlist(result$diagnostics$randomization_inference$p_values)[result$estimates$term]
      result$display$rows <- result$estimates
    }
  }
} else {
  if (!requireNamespace("DeclareDesign", quietly = TRUE)) fail("Install DeclareDesign for design diagnosis")
  sim <- o$simulation
  check_fields(sim, c("effect_grid", "arm_effects", "outcome_sd", "replications", "seed", "target_power"),
    c("icc", "adherence", "attrition", "test", "covariate_coefficients", "block_effects"), "simulation")
  grid <- unlist(sim$effect_grid)
  if (!is.numeric(grid) || length(grid) < 2L || any(!is.finite(grid)) || grid[1] != 0 || any(diff(grid) <= 0))
    fail("effect_grid must be finite, increasing, begin at zero and contain at least two effects")
  effects <- unlist(sim$arm_effects)
  if (!is.numeric(effects) || !setequal(names(effects), conditions) || any(!is.finite(effects)) || effects[conditions[1]] != 0)
    fail("arm_effects must give a finite effect loading for each condition and zero for reference")
  effects <- effects[conditions]
  outcome_sd <- number(sim$outcome_sd, "outcome_sd", .Machine$double.eps)
  B <- number(sim$replications, "replications", 2, Inf, TRUE)
  sim_seed <- number(sim$seed, "simulation seed", 0, .Machine$integer.max, TRUE)
  target_power <- number(sim$target_power, "target_power", alpha, 1)
  if (target_power %in% c(alpha, 1)) fail("target_power must be strictly between alpha and one")
  icc <- if (is.null(sim$icc)) 0 else number(sim$icc, "icc", 0, 1)
  if (icc > 0 && is.null(clusters)) fail("Positive ICC requires the declared cluster column")
  adherence <- if (is.null(sim$adherence)) setNames(rep(1, length(conditions)), conditions) else unlist(sim$adherence)
  if (!is.numeric(adherence) || !setequal(names(adherence), conditions) || any(!is.finite(adherence)) || any(adherence < 0 | adherence > 1))
    fail("adherence must give a probability for each condition")
  adherence <- adherence[conditions]
  attrition <- if (is.null(sim$attrition)) 0 else number(sim$attrition, "attrition", 0, 1 - .Machine$double.eps)
  test <- if (is.null(sim$test)) { if (balanced) "randomization" else "wald" } else sim$test
  if (balanced && test != "randomization") fail("Balanced design diagnosis uses the declared randomization test")
  if (!test %in% c("wald", "randomization") || (test == "randomization" && is.null(ri)))
    fail("simulation test must be wald, or randomization with declared RI options")
  baseline <- rep(0, N)
  if (!is.null(sim$covariate_coefficients)) {
    beta <- unlist(sim$covariate_coefficients)
    if (!is.numeric(beta) || !setequal(names(beta), covariates) || any(!is.finite(beta)))
      fail("covariate_coefficients must name every prespecified regressor")
    baseline <- baseline + drop(X %*% beta[covariates])
  }
  if (!is.null(sim$block_effects)) {
    beta <- unlist(sim$block_effects)
    if (!is.numeric(beta) || !setequal(names(beta), block_labels) || any(!is.finite(beta)))
      fail("block_effects must name each block")
    baseline <- baseline + beta[block_id]
  }
  summaries <- draws <- vector("list", length(grid))
  for (g in seq_along(grid)) {
    effect <- grid[g]
    model <- DeclareDesign::declare_model(handler = function(data = NULL) {
      dd <- d
      shock <- rnorm(N, sd = outcome_sd * sqrt(1 - icc))
      if (!is.null(clusters)) shock <- shock + rnorm(length(unique(clusters)), sd = outcome_sd * sqrt(icc))[match(clusters, unique(clusters))]
      dd$.ers_observed <- rbinom(N, 1, 1 - attrition) == 1
      for (j in seq_along(conditions)) {
        receipt <- rbinom(N, 1, adherence[j])
        dd[[paste0(".ers_receipt", j)]] <- receipt
        dd[[paste0(".ers_potential", j)]] <- baseline + shock + effect * effects[j] * receipt
      }
      dd
    })
    inquiry <- DeclareDesign::declare_inquiry(handler = function(data) {
      keep <- data$.ers_observed
      mu <- vapply(seq_along(conditions), function(j)
        weighted.mean(data[[paste0(".ers_potential", j)]][keep], weights[keep]), numeric(1))
      data.frame(inquiry = rownames(C), estimand = drop(C %*% mu))
    })
    assign <- DeclareDesign::declare_assignment(.ers_assignment = as.character(randomizr::conduct_ra(declaration)))
    measurement <- DeclareDesign::declare_measurement(handler = function(data) {
      potentials <- as.matrix(data[paste0(".ers_potential", seq_along(conditions))])
      data$.ers_observed_y <- potentials[cbind(seq_len(N), match(data$.ers_assignment, conditions))]
      data$.ers_observed_y[!data$.ers_observed] <- NA_real_
      receipts <- as.matrix(data[paste0(".ers_receipt", seq_along(conditions))])
      data$.ers_receipt <- receipts[cbind(seq_len(N), match(data$.ers_assignment, conditions))]
      data
    })
    estimator_step <- DeclareDesign::declare_estimator(handler = function(data) {
      rows <- estimate_outcome(data$.ers_observed_y, data$.ers_assignment)$rows
      ri_seed <- NA_integer_
      if (test == "randomization") {
        ri_seed <- as.integer((as.double(sample.int(1000000000L, 1L)) + ri$seed) %% .Machine$integer.max)
        rows$p_value <- unlist(randomization_test(data$.ers_observed_y, data$.ers_assignment, ri_seed)$p_values)
      }
      data.frame(inquiry = rows$term, term = rows$term, estimate = rows$estimate,
        std.error = rows$se, p.value = rows$p_value, conf.low = rows$ci_low,
        conf.high = rows$ci_high, observed_n = rows$n,
        observed_weight_total = sum(weights[data$.ers_observed]),
        observed_assignment_units = length(unique(assignment_id[data$.ers_observed])),
        active_receipt_rate = mean(data$.ers_receipt[data$.ers_assignment != conditions[1]]), ri_seed = ri_seed)
    })
    design <- model + inquiry + assign + measurement + estimator_step
    diagnosands <- DeclareDesign::declare_diagnosands(
      mean_estimand = mean(estimand), mean_estimate = mean(estimate),
      bias = mean(estimate - estimand), rmse = sqrt(mean((estimate - estimand)^2)),
      power = mean(p.value <= alpha), coverage = if (balanced) NA_real_ else mean(conf.low <= estimand & estimand <= conf.high),
      bias_mcse = sd(estimate - estimand) / sqrt(length(estimate)), mean_observed_n = mean(observed_n),
      mean_observed_weight_total = mean(observed_weight_total),
      mean_observed_assignment_units = mean(observed_assignment_units), mean_active_receipt_rate = mean(active_receipt_rate),
      alpha = alpha)
    # Same seed across effect values fixes model/assignment draws for grid comparisons.
    set.seed(sim_seed)
    diagnosis <- DeclareDesign::diagnose_design(design, sims = B, bootstrap_sims = 0L, diagnosands = diagnosands)
    dd <- as.data.frame(diagnosis$simulations_df)
    summary <- as.data.frame(diagnosis$diagnosands_df)
    if (("error" %in% names(dd) && any(dd$error %in% TRUE)) || any(summary$n_sims != B) || nrow(dd) != B * nrow(C)) {
      errors <- if ("error_message" %in% names(dd)) unique(na.omit(dd$error_message)) else "incomplete simulation rows"
      fail(paste("Design diagnosis did not complete every requested draw:", paste(errors, collapse = "; ")))
    }
    summary$effect <- effect
    summary$power_mcse <- sqrt(summary$power * (1 - summary$power) / B)
    summary$coverage_mcse <- sqrt(summary$coverage * (1 - summary$coverage) / B)
    dd$effect <- effect
    summaries[[g]] <- summary; draws[[g]] <- dd
  }
  power_rows <- do.call(rbind, summaries)
  mde_rows <- do.call(rbind, lapply(rownames(C), function(term) {
    rows <- power_rows[power_rows$term == term, ]
    at <- which(rows$power >= target_power)[1]
    scale <- if (is.na(at)) NA_real_ else rows$effect[at]
    data.frame(term = term, effect_scale = scale,
      assignment_itt = if (is.na(at)) NA_real_ else scale * sum(C[term, ] * effects * adherence),
      mean_simulated_itt = if (is.na(at)) NA_real_ else rows$mean_estimand[at],
      power = if (is.na(at)) NA_real_ else rows$power[at], attained = !is.na(at),
      lower_grid_effect = if (is.na(at) || at == 1L) NA_real_ else rows$effect[at - 1L])
  }))
  result$diagnostics$simulation <- list(specification = sim,
    target = "finite-population assignment ITT among units retained independently of assignment",
    adherence_model = "independent unit/arm Bernoulli receipt; assignment changes the received active-arm effect under exclusion",
    attrition_model = "MCAR retention drawn before assignment and fixed across potential outcomes",
    outcome_model = "baseline + Normal cluster shock + Normal individual shock + effect * arm_effects * receipt",
    test = test, alpha = alpha, coverage_available = !balanced, rng_kind = I(RNGkind()), seed = sim_seed,
    randomization = if (test == "randomization") list(specification = ri,
      seed_rule = "Each saved ri_seed is a draw from the DeclareDesign replication stream plus ri.seed, modulo R's integer maximum") else NULL,
    assignment_declaration_reused = TRUE, common_draws_across_effect_grid = TRUE,
    draws = do.call(rbind, draws), mde = mde_rows,
    mde_criterion = "smallest supplied effect_grid value whose simulated rejection frequency reaches target_power; no interpolation")
  result$adopted$experimental_design$simulation <- result$diagnostics$simulation[setdiff(names(result$diagnostics$simulation), c("draws", "mde"))]
  metadata$experimental_design <- result$adopted$experimental_design
  result$display <- list(kind = "power", rows = power_rows, metadata = metadata,
    display = list(plot_type = "line", x = "effect", y = "power", series = "term"))
  result$displays <- list(mde = list(kind = "table", rows = mde_rows, metadata = metadata))
  for (p in c("DeclareDesign", "fabricatr", "broom")) result$versions[[p]] <- as.character(packageVersion(p))
  result$signature$diagnose_design <- names(formals(DeclareDesign::diagnose_design))
}
result$native_fit <- list(format = "R-serialize-v3", data = base64_enc(serialize(native, NULL, version = 3)))
write_json(result, args[3], auto_unbox = TRUE, digits = 16, na = "null", null = "null", dataframe = "rows")
