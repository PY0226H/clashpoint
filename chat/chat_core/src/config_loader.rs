use anyhow::{bail, Context, Result};
use serde::de::DeserializeOwned;
use std::{
    env,
    fs::File,
    path::{Path, PathBuf},
};

pub fn load_yaml_with_fallback<T, P1, P2>(local_path: P1, etc_path: P2, env_key: &str) -> Result<T>
where
    T: DeserializeOwned,
    P1: AsRef<Path>,
    P2: AsRef<Path>,
{
    let local_path = local_path.as_ref();
    if let Ok(reader) = File::open(local_path) {
        return serde_yaml::from_reader(reader)
            .with_context(|| format!("failed to parse config: {}", local_path.display()));
    }

    let etc_path = etc_path.as_ref();
    if let Ok(reader) = File::open(etc_path) {
        return serde_yaml::from_reader(reader)
            .with_context(|| format!("failed to parse config: {}", etc_path.display()));
    }

    if let Ok(path) = env::var(env_key) {
        let path = PathBuf::from(path);
        let reader = File::open(&path).with_context(|| {
            format!("failed to open config from {}={}", env_key, path.display())
        })?;
        return serde_yaml::from_reader(reader)
            .with_context(|| format!("failed to parse config: {}", path.display()));
    }

    bail!(
        "Config file not found: local={}, etc={}, env={}",
        local_path.display(),
        etc_path.display(),
        env_key
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::Deserialize;
    use std::{
        fs, process,
        time::{SystemTime, UNIX_EPOCH},
    };

    #[derive(Debug, Deserialize, PartialEq, Eq)]
    struct TestConfig {
        value: i32,
    }

    fn unique_path(tag: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time should move forward")
            .as_nanos();
        env::temp_dir().join(format!(
            "echoisle-config-loader-{tag}-{}-{nanos}.yml",
            process::id()
        ))
    }

    fn write_yaml(path: &Path, value: i32) {
        fs::write(path, format!("value: {value}\n")).expect("write yaml");
    }

    fn cleanup(path: &Path) {
        let _ = fs::remove_file(path);
    }

    fn cleanup_env(key: &str) {
        env::remove_var(key);
    }

    #[test]
    fn load_yaml_with_fallback_should_prefer_local_over_etc_and_env() {
        let local = unique_path("local-priority-local");
        let etc = unique_path("local-priority-etc");
        let env_path = unique_path("local-priority-env");
        let env_key = format!("ECHOISLE_TEST_CONFIG_LOCAL_PRIORITY_{}", process::id());
        write_yaml(&local, 1);
        write_yaml(&etc, 2);
        write_yaml(&env_path, 3);
        env::set_var(&env_key, env_path.as_os_str());

        let cfg: TestConfig = load_yaml_with_fallback(&local, &etc, &env_key).expect("load local");
        assert_eq!(cfg, TestConfig { value: 1 });

        cleanup(&local);
        cleanup(&etc);
        cleanup(&env_path);
        cleanup_env(&env_key);
    }

    #[test]
    fn load_yaml_with_fallback_should_use_etc_when_local_missing() {
        let local_missing = unique_path("etc-fallback-local-missing");
        let etc = unique_path("etc-fallback-etc");
        write_yaml(&etc, 2);

        let cfg: TestConfig = load_yaml_with_fallback(
            &local_missing,
            &etc,
            "ECHOISLE_TEST_CONFIG_UNUSED_ENV_ETC_FALLBACK",
        )
        .expect("load etc");
        assert_eq!(cfg, TestConfig { value: 2 });

        cleanup(&etc);
    }

    #[test]
    fn load_yaml_with_fallback_should_use_env_when_files_missing() {
        let local_missing = unique_path("env-fallback-local-missing");
        let etc_missing = unique_path("env-fallback-etc-missing");
        let env_path = unique_path("env-fallback-env");
        let env_key = format!("ECHOISLE_TEST_CONFIG_ENV_FALLBACK_{}", process::id());
        write_yaml(&env_path, 3);
        env::set_var(&env_key, env_path.as_os_str());

        let cfg: TestConfig =
            load_yaml_with_fallback(&local_missing, &etc_missing, &env_key).expect("load env");
        assert_eq!(cfg, TestConfig { value: 3 });

        cleanup(&env_path);
        cleanup_env(&env_key);
    }

    #[test]
    fn load_yaml_with_fallback_should_error_when_all_sources_missing() {
        let local_missing = unique_path("none-local-missing");
        let etc_missing = unique_path("none-etc-missing");
        let env_key = format!("ECHOISLE_TEST_CONFIG_MISSING_{}", process::id());
        cleanup_env(&env_key);

        let err =
            load_yaml_with_fallback::<TestConfig, _, _>(&local_missing, &etc_missing, &env_key)
                .expect_err("should fail when config missing");
        assert!(err.to_string().contains("Config file not found"));
    }
}
