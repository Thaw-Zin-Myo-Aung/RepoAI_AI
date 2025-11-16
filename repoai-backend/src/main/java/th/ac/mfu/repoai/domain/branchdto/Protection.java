package th.ac.mfu.repoai.domain.branchdto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Protection(
        Boolean enabled,
        @JsonProperty("required_status_checks") RequiredStatusChecks requiredStatusChecks) {
}