package th.ac.mfu.repoai.domain.branchdto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record RequiredStatusChecks(
        @JsonProperty("enforcement_level") String enforcementLevel,
        List<String> contexts,
        List<Object> checks) {
}