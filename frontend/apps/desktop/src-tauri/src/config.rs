use anyhow::Result;
use config::{Config, File, FileFormat};
use dirs::config_dir;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct ServerConfig {
    pub chat: String,
    pub notification: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IapConfig {
    #[serde(default = "default_iap_purchase_mode")]
    pub purchase_mode: String,
    #[serde(default)]
    pub allowed_product_ids: Vec<String>,
    #[serde(default)]
    pub native_bridge: IapNativeBridgeConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct IapNativeBridgeConfig {
    #[serde(default)]
    pub bin: String,
    #[serde(default)]
    pub args: Vec<String>,
}

impl Default for IapConfig {
    fn default() -> Self {
        Self {
            purchase_mode: default_iap_purchase_mode(),
            allowed_product_ids: vec![],
            native_bridge: IapNativeBridgeConfig::default(),
        }
    }
}

fn default_iap_purchase_mode() -> String {
    "mock".to_string()
}

/// app config
#[derive(Debug, Serialize, Deserialize)]
pub struct AppConfig {
    pub server: ServerConfig,
    #[serde(default)]
    pub iap: IapConfig,
}

impl AppConfig {
    pub fn try_new() -> Result<Self> {
        let config_file = config_dir()
            .expect("config directory not found")
            .join("app.yml");
        let default_config = include_str!("./fixtures/config.default.yml");
        let config = Config::builder()
            .add_source(File::from_str(default_config, FileFormat::Yaml))
            .add_source(File::with_name(&config_file.to_string_lossy()).required(false))
            .build()?;

        Ok(config.try_deserialize()?)
    }
}
