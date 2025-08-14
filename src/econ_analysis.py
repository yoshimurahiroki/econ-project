"""経済分析用のユーティリティ関数集"""

from typing import Optional, Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats


class EconAnalyzer:
    """経済分析のためのクラス"""
    
    def __init__(self, data: pd.DataFrame) -> None:
        """
        初期化
        
        Args:
            data: 分析対象のデータフレーム
        """
        self.data = data
    self.models: dict[str, Any] = {}
    
    def mincer_regression(
        self, 
        dependent_var: str,
        education_var: str,
        experience_var: str,
        add_experience_squared: bool = True
    ) -> sm.regression.linear_model.RegressionResultsWrapper:
        """
        Mincer型賃金関数の推定
        
        Args:
            dependent_var: 被説明変数（通常は対数賃金）
            education_var: 教育変数
            experience_var: 経験変数
            add_experience_squared: 経験の2乗項を追加するかどうか
            
        Returns:
            回帰結果
        """
        # 説明変数の準備
        X_vars = [education_var, experience_var]
        
        if add_experience_squared:
            exp_sq_name = f"{experience_var}_squared"
            self.data[exp_sq_name] = self.data[experience_var] ** 2
            X_vars.append(exp_sq_name)
        
        # 回帰分析の実行
        X = sm.add_constant(self.data[X_vars])
        y = self.data[dependent_var]
        
        model = sm.OLS(y, X).fit()
        
        # 結果を保存
        model_name = f"mincer_{dependent_var}"
        self.models[model_name] = model
        
        return model
    
    def calculate_returns_to_education(
        self,
        model: sm.regression.linear_model.RegressionResultsWrapper,
        education_var: str,
    ) -> dict[str, float]:
        """
        教育収益率を計算
        
        Args:
            model: 回帰結果
            education_var: 教育変数名
            
        Returns:
            収益率の情報
        """
        coef = model.params[education_var]
        std_err = model.bse[education_var]
        t_stat = model.tvalues[education_var]
        p_value = model.pvalues[education_var]
        
        return {
            'coefficient': coef,
            'return_percent': coef * 100,
            'std_error': std_err,
            't_statistic': t_stat,
            'p_value': p_value,
            'significant_5pct': p_value < 0.05
        }
    
    def descriptive_stats(
        self,
        variables: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        記述統計の計算
        
        Args:
            variables: 対象変数のリスト（Noneの場合は全数値変数）
            
        Returns:
            記述統計のデータフレーム
        """
        if variables is None:
            variables = self.data.select_dtypes(include=[np.number]).columns.tolist()
        
        stats_df = self.data[variables].describe()
        
        # 追加の統計量
        additional_stats = {}
        for var in variables:
            additional_stats[var] = {
                'skewness': stats.skew(self.data[var].dropna()),
                'kurtosis': stats.kurtosis(self.data[var].dropna()),
                'missing': self.data[var].isna().sum()
            }
        
        additional_df = pd.DataFrame(additional_stats).T
        stats_df = pd.concat([stats_df.T, additional_df], axis=1)
        
        return stats_df


def simulate_wage_data(
    n_obs: int = 1000,
    seed: int | None = None,
) -> pd.DataFrame:
    """
    賃金データのシミュレーション
    
    Args:
        n_obs: サンプルサイズ
        seed: 乱数シード
        
    Returns:
        シミュレートされたデータ
    """
    if seed is not None:
        np.random.seed(seed)
    
    # 説明変数の生成
    education = np.random.normal(12, 3, n_obs)
    education = np.clip(education, 6, 20)  # 6-20年の範囲
    
    experience = np.random.uniform(0, 40, n_obs)
    age = education + experience + np.random.normal(6, 2, n_obs)
    age = np.clip(age, 18, 70)
    
    # 賃金の生成（Mincer型）
    log_wage = (2.5 + 
                0.1 * education + 
                0.05 * experience - 
                0.001 * (experience ** 2) + 
                np.random.normal(0, 0.3, n_obs))
    
    wage = np.exp(log_wage)
    
    return pd.DataFrame({
        'wage': wage,
        'log_wage': log_wage,
        'education': education,
        'experience': experience,
        'age': age
    })


def robust_regression_summary(
    models: list[sm.regression.linear_model.RegressionResultsWrapper],
    model_names: list[str],
) -> pd.DataFrame:
    """
    複数のモデルの結果をまとめて表示
    
    Args:
        models: 回帰結果のリスト
        model_names: モデル名のリスト
        
    Returns:
        結果をまとめたデータフレーム
    """
    if len(models) != len(model_names):
        raise ValueError("models and model_names must have the same length")
    
    summary_data = {}
    
    for model, name in zip(models, model_names, strict=False):
        summary_data[name] = {
            'R-squared': model.rsquared,
            'Adj R-squared': model.rsquared_adj,
            'F-statistic': model.fvalue,
            'F p-value': model.f_pvalue,
            'AIC': model.aic,
            'BIC': model.bic,
            'N observations': model.nobs
        }
    
    return pd.DataFrame(summary_data).T


if __name__ == "__main__":
    # サンプル使用例
    print("=== Wage Analysis Example ===")
    
    # データの生成
    data = simulate_wage_data(n_obs=1000, seed=42)
    print(f"Generated data with {len(data)} observations")
    
    # 分析器の初期化
    analyzer = EconAnalyzer(data)
    
    # 記述統計
    desc_stats = analyzer.descriptive_stats()
    print("\nDescriptive Statistics:")
    print(desc_stats.round(3))
    
    # Mincer回帰
    model = analyzer.mincer_regression(
        dependent_var='log_wage',
        education_var='education',
        experience_var='experience'
    )
    
    print("\nMincer Regression Results:")
    print(model.summary())
    
    # 教育収益率
    returns = analyzer.calculate_returns_to_education(model, 'education')
    print(f"\nReturns to Education: {returns['return_percent']:.2f}%")
    print(f"Significant at 5%: {returns['significant_5pct']}")
