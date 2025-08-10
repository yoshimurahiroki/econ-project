# 経済分析用Rユーティリティ関数集
# Econometric Analysis Utilities in R

# 必要なライブラリの読み込み
library(tidyverse)
library(broom)
library(stargazer)
library(ggplot2)
library(corrplot)

#' サンプル賃金データの生成
#' 
#' @param n サンプルサイズ
#' @param seed 乱数シード
#' @return 賃金データのdata.frame
generate_wage_data <- function(n = 1000, seed = 42) {
  set.seed(seed)
  
  # 説明変数の生成
  education <- pmax(6, pmin(20, rnorm(n, mean = 12, sd = 3)))
  experience <- runif(n, min = 0, max = 40)
  age <- education + experience + pmax(0, rnorm(n, mean = 6, sd = 2))
  age <- pmin(70, pmax(18, age))
  
  # Mincer型賃金関数
  log_wage <- 2.5 + 0.1 * education + 0.05 * experience - 0.001 * experience^2 + rnorm(n, 0, 0.3)
  wage <- exp(log_wage)
  
  data.frame(
    wage = wage,
    log_wage = log_wage,
    education = education,
    experience = experience,
    age = age
  )
}

#' Mincer型賃金関数の推定
#' 
#' @param data データフレーム
#' @param dependent 被説明変数名
#' @param education_var 教育変数名
#' @param experience_var 経験変数名
#' @param add_squared 経験の2乗項を追加するか
#' @return lm オブジェクト
estimate_mincer <- function(data, dependent = "log_wage", 
                          education_var = "education", 
                          experience_var = "experience",
                          add_squared = TRUE) {
  
  # 基本的な式
  formula_str <- paste(dependent, "~", education_var, "+", experience_var)
  
  # 経験の2乗項を追加
  if (add_squared) {
    exp_sq_name <- paste0(experience_var, "_sq")
    data[[exp_sq_name]] <- data[[experience_var]]^2
    formula_str <- paste(formula_str, "+", exp_sq_name)
  }
  
  # 回帰分析の実行
  formula_obj <- as.formula(formula_str)
  model <- lm(formula_obj, data = data)
  
  return(model)
}

#' 教育収益率の計算
#' 
#' @param model lmオブジェクト
#' @param education_var 教育変数名
#' @return 教育収益率の情報リスト
calculate_education_returns <- function(model, education_var = "education") {
  coef_summary <- summary(model)$coefficients
  
  if (!education_var %in% rownames(coef_summary)) {
    stop(paste("Variable", education_var, "not found in model"))
  }
  
  coef_val <- coef_summary[education_var, "Estimate"]
  std_err <- coef_summary[education_var, "Std. Error"]
  t_val <- coef_summary[education_var, "t value"]
  p_val <- coef_summary[education_var, "Pr(>|t|)"]
  
  list(
    coefficient = coef_val,
    return_percent = coef_val * 100,
    std_error = std_err,
    t_statistic = t_val,
    p_value = p_val,
    significant_5pct = p_val < 0.05
  )
}

#' 記述統計の拡張版計算
#' 
#' @param data データフレーム
#' @param vars 対象変数（NULLの場合は数値変数全て）
#' @return 記述統計のデータフレーム
enhanced_summary <- function(data, vars = NULL) {
  if (is.null(vars)) {
    vars <- names(data)[sapply(data, is.numeric)]
  }
  
  # 基本統計量
  basic_stats <- data %>%
    select(all_of(vars)) %>%
    summarise_all(list(
      mean = ~ mean(.x, na.rm = TRUE),
      sd = ~ sd(.x, na.rm = TRUE),
      min = ~ min(.x, na.rm = TRUE),
      q25 = ~ quantile(.x, 0.25, na.rm = TRUE),
      median = ~ median(.x, na.rm = TRUE),
      q75 = ~ quantile(.x, 0.75, na.rm = TRUE),
      max = ~ max(.x, na.rm = TRUE),
      skewness = ~ moments::skewness(.x, na.rm = TRUE),
      kurtosis = ~ moments::kurtosis(.x, na.rm = TRUE),
      missing = ~ sum(is.na(.x))
    )) %>%
    pivot_longer(everything(), names_to = "var_stat", values_to = "value") %>%
    separate(var_stat, into = c("variable", "statistic"), sep = "_(?=[^_]*$)") %>%
    pivot_wider(names_from = statistic, values_from = value)
  
  return(basic_stats)
}

#' 複数モデルの比較表作成
#' 
#' @param models lmオブジェクトのリスト
#' @param model_names モデル名のベクトル
#' @return 比較表のデータフレーム
model_comparison_table <- function(models, model_names = NULL) {
  if (is.null(model_names)) {
    model_names <- paste0("Model_", seq_along(models))
  }
  
  if (length(models) != length(model_names)) {
    stop("Length of models and model_names must be the same")
  }
  
  comparison_data <- map2_dfr(models, model_names, function(model, name) {
    model_summary <- summary(model)
    
    data.frame(
      Model = name,
      R_squared = model_summary$r.squared,
      Adj_R_squared = model_summary$adj.r.squared,
      F_statistic = model_summary$fstatistic[1],
      F_p_value = pf(model_summary$fstatistic[1], 
                     model_summary$fstatistic[2], 
                     model_summary$fstatistic[3], 
                     lower.tail = FALSE),
      AIC = AIC(model),
      BIC = BIC(model),
      N_obs = nobs(model)
    )
  })
  
  return(comparison_data)
}

#' 賃金データの可視化
#' 
#' @param data データフレーム
#' @return ggplotオブジェクトのリスト
visualize_wage_data <- function(data) {
  plots <- list()
  
  # 1. 賃金分布
  plots$wage_dist <- ggplot(data, aes(x = wage)) +
    geom_histogram(bins = 30, fill = "skyblue", alpha = 0.7) +
    labs(title = "賃金分布", x = "賃金", y = "頻度") +
    theme_minimal()
  
  # 2. 対数賃金分布
  plots$log_wage_dist <- ggplot(data, aes(x = log_wage)) +
    geom_histogram(bins = 30, fill = "lightgreen", alpha = 0.7) +
    labs(title = "対数賃金分布", x = "対数賃金", y = "頻度") +
    theme_minimal()
  
  # 3. 教育vs対数賃金
  plots$education_wage <- ggplot(data, aes(x = education, y = log_wage)) +
    geom_point(alpha = 0.6) +
    geom_smooth(method = "lm", color = "red") +
    labs(title = "教育年数と対数賃金", x = "教育年数", y = "対数賃金") +
    theme_minimal()
  
  # 4. 経験vs対数賃金
  plots$experience_wage <- ggplot(data, aes(x = experience, y = log_wage)) +
    geom_point(alpha = 0.6) +
    geom_smooth(method = "loess", color = "blue") +
    labs(title = "経験年数と対数賃金", x = "経験年数", y = "対数賃金") +
    theme_minimal()
  
  # 5. 相関行列のヒートマップ
  cor_data <- data %>% 
    select(log_wage, education, experience, age) %>%
    cor(use = "complete.obs")
  
  plots$correlation <- corrplot::corrplot(cor_data, method = "color", 
                                        title = "変数間相関", 
                                        mar = c(0,0,1,0))
  
  return(plots)
}

# デモンストレーション用の関数
run_wage_analysis_demo <- function() {
  cat("=== R による賃金分析デモ ===\n\n")
  
  # データ生成
  cat("1. データ生成中...\n")
  data <- generate_wage_data(n = 1000, seed = 42)
  cat("   生成されたサンプル数:", nrow(data), "\n\n")
  
  # 記述統計
  cat("2. 記述統計\n")
  desc_stats <- enhanced_summary(data)
  print(desc_stats)
  cat("\n")
  
  # 回帰分析
  cat("3. Mincer回帰の実行\n")
  
  # シンプルモデル
  model1 <- estimate_mincer(data, add_squared = FALSE)
  cat("   シンプルモデル (education + experience):\n")
  print(summary(model1)$coefficients)
  cat("\n")
  
  # 完全モデル
  model2 <- estimate_mincer(data, add_squared = TRUE)
  cat("   完全モデル (education + experience + experience^2):\n")
  print(summary(model2)$coefficients)
  cat("\n")
  
  # 教育収益率
  cat("4. 教育収益率\n")
  returns1 <- calculate_education_returns(model1)
  returns2 <- calculate_education_returns(model2)
  
  cat("   シンプルモデル:", sprintf("%.2f%%", returns1$return_percent), 
      "(p-value:", sprintf("%.4f", returns1$p_value), ")\n")
  cat("   完全モデル:", sprintf("%.2f%%", returns2$return_percent), 
      "(p-value:", sprintf("%.4f", returns2$p_value), ")\n\n")
  
  # モデル比較
  cat("5. モデル比較\n")
  comparison <- model_comparison_table(
    list(model1, model2), 
    c("Simple", "Full")
  )
  print(comparison)
  cat("\n")
  
  # 可視化
  cat("6. 可視化の作成\n")
  plots <- visualize_wage_data(data)
  cat("   作成されたプロット数:", length(plots), "\n")
  
  return(list(
    data = data,
    models = list(simple = model1, full = model2),
    plots = plots,
    comparison = comparison
  ))
}

# スクリプトが直接実行された場合のテスト
if (sys.nframe() == 0) {
  # デモの実行
  result <- run_wage_analysis_demo()
  cat("\n=== 分析完了 ===\n")
}
