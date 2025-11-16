package th.ac.mfu.repoai.domain.branchdto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record RequiredCheck(String context, @JsonProperty("app_id") Long app_id) {
}
