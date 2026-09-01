# Research Citations & References

Academic and industry sources supporting this project's methodology.

## Time Series & Forecasting

1. **Box, G. E., Jenkins, G. M., & Reinsel, G. C. (2015).** *Time Series Analysis: Forecasting and Control* (5th ed.). John Wiley & Sons.
   - ARIMA theory foundation
   - Stationarity testing (ADF test)
   - Forecasting confidence intervals

2. **Bergmeir, C., & Benítez, J. M. (2012).** On the Use of Cross-Validation for Time Series Forecasting Evaluation. *Information Sciences*, 191, 192–213.
   - Walk-forward cross-validation methodology
   - Temporal order preservation
   - Comparison with K-fold (inappropriate for time series)

3. **Hyndman, R. J., & Athanasopoulos, G. (2021).** *Forecasting: Principles and Practice* (3rd ed.). OTexts.
   - Auto-ARIMA selection
   - Forecast accuracy measures (RMSE, MAE)
   - Evaluation of ensemble methods

## Machine Learning & Ensemble Methods

4. **Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., ... & Liu, T. Y. (2017).** LightGBM: A Fast, Distributed, High Performance Gradient Boosting Framework. *Proceedings of the 31st Conference on Neural Information Processing Systems (NeurIPS)*, 3149–3157.
   - LightGBM algorithm details
   - Leaf-wise tree growth
   - Handling imbalanced data

5. **Chen, T., & Guestrin, C. (2016).** XGBoost: A Scalable Tree Boosting System. *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*, 785–794.
   - Gradient boosting theory
   - Regularization techniques
   - Feature importance extraction

6. **Lundberg, S. M., & Lee, S. I. (2017).** A Unified Approach to Interpreting Model Predictions. *Advances in Neural Information Processing Systems*, 30, 4765–4774.
   - SHAP (SHapley Additive exPlanations) values
   - Model-agnostic feature importance
   - Local vs. global explanations

## Agricultural Applications

7. **Albrigo, L. G., Paramasivam, S., & Alves, M. C. (2005).** Growing Degree Days: A Tool for Citrus Management. In *Citrus Management*. University of Florida IFAS Extension.
   - GDD calculation methodology
   - Base temperature 50°F for citrus ripening
   - Historical GDD targets by variety

8. **Ziegler, C. R., & Bruton, B. D. (2009).** Weather and Climate Effects on Horticultural Crops. *HortScience*, 44(7), 1545–1550.
   - Temperature stress thresholds
   - Precipitation patterns & disease
   - Frost risk during bloom

9. **Gottwald, T. R., Ploetz, R. C., & McSorley, R. (2002).** Citrus Canker: The Pathogen and Its Impact. *Plant Health Progress*.
   - Citrus disease epidemiology
   - Frost as predisposing factor for disease entry
   - Weather-disease interactions

## Citrus-Specific Research

10. **Singerman, A., & Useche, P. (2016).** The Impact of Citrus Greening Disease (Huanglongbing) on Citrus Grower Profitability in Florida. *Journal of Agricultural and Applied Economics*, 48(2), 154–171.
    - Economic impact quantification
    - Grower profit margins
    - Long-term yield decline modeling

11. **Rogers, M. E. (2015).** Citrus Greening (Huanglongbing): An Overview. *Citrus Research Board*.
    - HLB biology and transmission
    - Vector (Asian citrus psyllid) behavior
    - Latent period effects on yield

12. **Schumann, A. W., & Singerman, A. (2016).** Framework for Valuation of Huanglongbing Control Strategies. *EDIS*.
    - Cost-benefit analysis of control strategies
    - Impact on yield forecasting models
    - Long-term profitability

13. **Bassanezi, R. B., Bergamin Filho, A., & Amorim, L. (2006).** Quantifying the Temporal Rate of Change of Huanglongbing Symptoms in Sweet Orange Trees Inoculated with Candidatus Liberibacter asiaticus. *Phytopathology*, 96(12), 1274–1280.
    - HLB symptom progression
    - Yield loss timeline (typically 3-5 years post-infection)
    - Infection curve modeling

## Climate & Weather

14. **Thornton, P. K. (2012).** Recalibrating Food Production in the Face of Climate Change: Flooring the Losses, Raising the Gains. *Global Food Security*, 1(1), 49–57.
    - Climate variability impact on crops
    - Adaptation strategies
    - Weather risk assessment

15. **Lobell, D. B., & Field, C. B. (2007).** Global Scale Climate–Crop Yield Relationships and Adaptation Options. *Global Change Biology*, 13(8), 1683–1695.
    - Weather elasticity of crop yields
    - Temperature thresholds
    - Precipitation nonlinearity

## Data Science Techniques

16. **Goodfellow, I., Bengio, Y., & Courville, A. (2016).** *Deep Learning*. MIT Press.
    - Normalization & standardization
    - Overfitting prevention
    - Cross-validation strategies

17. **Hastie, T., Tibshirani, R., & Friedman, J. (2009).** *The Elements of Statistical Learning* (2nd ed.). Springer.
    - Regression methodology
    - Feature selection
    - Model evaluation metrics

## Data Sources (Primary)

18. **USDA NASS (2024).** QuickStats Agricultural Statistics Database. U.S. Department of Agriculture, National Agricultural Statistics Service.
    - https://quickstats.nass.usda.gov/
    - Commodity production data
    - County-level aggregates

19. **NOAA NCEI (2024).** Global Summary of the Day. National Oceanic and Atmospheric Administration, National Centers for Environmental Information.
    - https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-day
    - Weather observations
    - Historical climate data

20. **USDA ERS (2024).** Citrus Yearbook Tables. Economic Research Service.
    - https://www.ers.usda.gov/webdocs/publications/
    - Production trends
    - Economic analysis

## Industry Reports

21. **USDA (2023).** Florida Citrus: Situation and Outlook Reports. U.S. Department of Agriculture.
    - Production forecasts
    - Market analysis
    - Policy discussions

22. **Citrus Processors Association (2023).** Citrus Production Trends in Florida.
    - Market size
    - Grower economics
    - Export data

23. **University of Florida IFAS Extension (2024).** Citrus Management Publications.
    - https://crec.ifas.ufl.edu/
    - Practical guidelines
    - Research updates

## Software & Libraries

24. **McKinney, W. (2010).** Data Structures for Statistical Computing in Python. *Proceedings of the 9th Python in Science Conference*, 51–56.
    - Pandas library documentation
    - DataFrame operations
    - Time series handling

25. **Plotly Technologies Inc. (2024).** Plotly Open Source Graphing Libraries.
    - https://plotly.com/python/
    - Interactive visualization
    - Dash framework

26. **Harris, C. R., et al. (2020).** Array Programming with NumPy. *Nature*, 585, 357–362.
    - NumPy array operations
    - Numerical computations

## Methodology References

27. **Diebold, F. X., & Mariano, R. S. (2002).** Comparing Predictive Accuracy. *Journal of Business & Economic Statistics*, 20(1), 134–144.
    - Forecast evaluation metrics
    - RMSE vs. MAE comparison
    - Directional accuracy

28. **Granger, C. W. (1969).** Investigating Causal Relations by Econometric Models and Cross-spectral Methods. *Econometrica*, 37(3), 424–438.
    - Causality testing
    - Granger causality
    - Lag structure selection

---

## Online Resources

### USDA & Federal
- USDA NASS QuickStats: https://quickstats.nass.usda.gov/
- USDA ERS Citrus: https://www.ers.usda.gov/webdocs/publications/
- USDA APHIS HLB Info: https://www.aphis.usda.gov/citrus-greening

### NOAA & Climate
- NOAA CDO Web: https://www.ncei.noaa.gov/cdo-web/
- Global Summary of the Day: https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-day
- NOAA Climate Data: https://www.ncei.noaa.gov/access/metadata/

### Academic & Research
- University of Florida CREC: https://crec.ifas.ufl.edu/
- Citrus Research Board: https://www.citrusresearch.org/
- Google Scholar (Citrus Greening): https://scholar.google.com/scholar?q=citrus+greening

### Data Science
- Scikit-learn Documentation: https://scikit-learn.org/
- LightGBM Documentation: https://lightgbm.readthedocs.io/
- Statsmodels ARIMA: https://www.statsmodels.org/dev/generated/statsmodels.tsa.arima.model.ARIMA.html

---

## How to Cite This Project

### APA Format
```
Agricultural Data Science Team. (2026). Florida Citrus Yield Forecasting System: 
USDA NASS + NOAA weather ensemble ML. GitHub. 
https://github.com/yourusername/florida-citrus-yield-forecast
```

### BibTeX
```bibtex
@software{citrus_forecast_2026,
  title={Florida Citrus Yield Forecasting System},
  author={Agricultural Data Science Team},
  year={2026},
  url={https://github.com/yourusername/florida-citrus-yield-forecast},
  note={USDA NASS + NOAA weather ensemble ML pipeline}
}
```

### Chicago Format
```
Agricultural Data Science Team. "Florida Citrus Yield Forecasting System: 
USDA NASS + NOAA Weather Ensemble ML." GitHub repository. Accessed July 2026. 
https://github.com/yourusername/florida-citrus-yield-forecast.
```

---

## Contact & Questions

For questions about citations or methodology:
- Email: brian.blitz28@gmail.com
- GitHub Issues: https://github.com/yourusername/florida-citrus-yield-forecast/issues
- Research Discussions: https://github.com/yourusername/florida-citrus-yield-forecast/discussions

---

**Last Updated**: July 2026  
**Total References**: 28  
**Subject Areas**: Time Series, ML/AI, Agronomy, Climate, Economics, Software

