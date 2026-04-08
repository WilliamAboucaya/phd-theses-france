# R packages required for this project
# Install all with: source("requirements_r.R")
# Equivalent of pyproject.toml / uv.lock for R dependencies

required_packages <- c(
  # data wrangling
  "arrow",       # read/write parquet files
  "dplyr",       # data manipulation
  "tidyr",       # reshaping
  "stringr",     # string operations
  "naniar",      # missing data handling

  # modelling
  "lavaan",      # multigroup SEM and invariance tests
  "sandwich",    # HC3 robust standard errors for lavaan
  "interactions", # Johnson-Neyman intervals

  # visualisation
  "ggplot2",     # plots
  "patchwork"    # combine multiple ggplots side by side
)

missing <- required_packages[!required_packages %in% installed.packages()[, "Package"]]

if (length(missing) > 0) {
  message("Installing missing packages: ", paste(missing, collapse = ", "))
  install.packages(missing)
} else {
  message("All R packages already installed.")
}
